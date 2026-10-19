"""Integration coverage for the READ-ONLY treatment of a done track (SPECIFICATION v061).

A DONE TRACK is a track holding a standing ``done`` declaration, or a plan track whose
plan directory is archived while its recorded session still exists. The daemon performs
NO act on one: every observation is read-only exactly as the ``list`` path is, so the
track's state file, its round record and its pane are all left alone.

These tests drive the PUBLIC daemon surface (``tick``) rather than ``evaluate``, because
the gaps the rule closes are NOT in the cascade's own ``done`` leg — they are in the
prologue and the pair pass that run around it: the self-healing resume retry, the
held-delivery release, the compaction-latch record and the supervisor pair.
"""

from __future__ import annotations

import contextlib
import io as _io
import shutil

import _supervisor_config
import registry
import signals
import supervisor
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    unsubmitted_resume_capture,
    write_fresh_supervisor_state,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# The live Claude process the fixture registry describes.
SESSION_PID = 200
SESSION_PROC_START = "pt"


def archive_plan(*, repo, topic):
    """`git mv plan/<topic> plan/archive/<topic>` — the move that ends discovery."""
    archive = repo / "plan" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    _ = shutil.move(str(repo / "plan" / topic), str(archive / topic))


def mapped_plan_track(*, tmp_path, repo_name, capture, now=1000.0):
    """A mapped Claude plan track a whole acting ``tick`` can drive.

    The Claude session registry is REAL here rather than pre-seeded on the Supervisor:
    ``build_rows`` recomputes ``claude_status_by_session`` from ``sessions_dir`` at the
    top of every tick, so a pre-seeded map is overwritten and a track with no live
    Claude status never reaches the wrap-up branch these tests have to suppress.
    """
    repo, topic = make_plan(tmp_path=tmp_path, repo_name=repo_name)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    sessions_dir = tmp_path / repo_name / "sessions"
    sessions_dir.mkdir(parents=True)
    write_session(sessions_dir=sessions_dir, pid=SESSION_PID, name=topic, cwd=repo)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=capture)
    fake.pane_pids = {100: session}
    sup = make_supervisor(
        tmp_path=tmp_path / repo_name,
        fake=fake,
        watch_repos=[str(repo)],
        own_pane="%7",
        now=lambda: now,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {SESSION_PID: 100}.get(pid),
        starttime_of=lambda *, pid: {SESSION_PID: SESSION_PROC_START}.get(pid),
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=session),
        store_path=sup.store_path,
        added_at="2026-10-19T00:00:00Z",
    )
    return repo, topic, session, fake, sup


def live_identity(*, topic):
    """The identity the daemon derives for the fixture's registry-backed session.

    `claude:<pid>:<procStart>:<topic>`, taken from the registry file the fixture writes.
    A round or a resume-pending record keyed on anything else is a PREDECESSOR's, which
    the daemon treats as a stale round rather than as the live one under test.
    """
    return f"claude:{SESSION_PID}:{SESSION_PROC_START}:{topic}"


def test_scenario_a_done_track_receives_no_act_on_any_path(*, tmp_path):
    """A done track whose round has a band due, whose pending resume would be retried,
    and whose compaction latch would fire, receives nothing at all."""
    repo, topic, session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path,
        repo_name="stranded",
        capture=unsubmitted_resume_capture(ctx=10, repo=str(tmp_path / "stranded")),
    )
    identity = live_identity(topic=topic)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=900.0, session_identity=identity, stamp_path=sup.stamp_path
    )
    registry.set_resume_pending(
        repo=str(repo), topic=topic, session_identity=identity, stamp_path=sup.stamp_path
    )
    _ = registry.record_context_compaction(
        repo=str(repo),
        topic=topic,
        record=registry.ContextCompaction(
            session_identity=identity, watermark_ctx=9, latched_at=800.0, from_ctx=9, to_ctx=90
        ),
        store_path=sup.store_path,
    )
    state = signals.state_path(repo=str(repo), topic=topic)
    _ = declare(repo=repo, topic=topic, value="done: release complete", mtime=950.0)
    state_before = state.read_bytes()
    round_before = registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    row = next(view for view in views if view.topic == topic)
    assert row.status == signals.STATE_DONE
    assert supervisor.needs_attention(row=row) is False
    assert fake.paste_texts() == []
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert state.read_bytes() == state_before
    assert (
        registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == round_before
    )
    # The retry leg was ELIGIBLE and skipped, not satisfied: the round is still
    # resume-pending, which is what a consumed declaration would have cleared.
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)


def test_scenario_an_archived_plan_whose_session_still_exists_receives_nothing(*, tmp_path):
    """Retention is for VISIBILITY only. An archived plan whose recorded session is
    still live is a done track: it is observed read-only and renders the quiet `done`
    row outside the attention set, whatever its own state file holds."""
    repo, topic, session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path, repo_name="archived", capture=idle_capture(ctx=40)
    )
    # A MALFORMED value, deliberately: a track that is done because its plan is
    # archived is an attention member only through live gate evidence, so the
    # `BAD state file` note must not put this row in NEEDS YOU either.
    state = declare(repo=repo, topic=topic, value="working", mtime=950.0)
    archive_plan(repo=repo, topic=topic)
    state_before = state.read_bytes()

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    row = next(view for view in views if view.topic == topic)
    assert row.status == signals.STATE_DONE
    assert row.archived_live is True
    assert supervisor.needs_attention(row=row) is False
    assert fake.paste_texts() == []
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert fake.session_exists(session=session) is True
    assert state.read_bytes() == state_before


def picker_capture(*, ctx):
    """A pane sitting on an open structured picker — live gate evidence."""
    return f"Choose the next action\n❯ 1. Publish\n  2. Wait\n  Ctx: {ctx}% left\n"


def test_scenario_an_archived_plan_showing_a_picker_is_surfaced_but_not_acted_on(*, tmp_path):
    """Live gate evidence outranks `done` for REPORTING and for reporting only: the row
    is a blocked attention member, and still nothing is delivered to the pane."""
    repo, topic, _session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path, repo_name="archived-picker", capture=picker_capture(ctx=72)
    )
    archive_plan(repo=repo, topic=topic)

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    row = next(view for view in views if view.topic == topic)
    assert row.status == "blocked:human"
    assert row.archived_live is True
    assert supervisor.needs_attention(row=row) is True
    assert fake.paste_texts() == []
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")


def test_a_declared_done_track_showing_a_picker_is_surfaced_but_not_acted_on(*, tmp_path):
    """The declaration arm of the same rule: a track that is done by its own `done` and
    is sitting on a picker reports `blocked:human` without being acted on either."""
    repo, topic, _session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path, repo_name="done-picker", capture=picker_capture(ctx=72)
    )
    state = declare(repo=repo, topic=topic, value="done: release complete", mtime=950.0)
    state_before = state.read_bytes()

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)

    row = next(view for view in views if view.topic == topic)
    assert row.status == "blocked:human"
    assert supervisor.needs_attention(row=row) is True
    assert fake.paste_texts() == []
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
    assert state.read_bytes() == state_before


def test_scenario_a_done_track_whose_session_clears_its_own_declaration_is_supervised_again(
    *, tmp_path
):
    """Re-opening is explicit and costs the round nothing: the floor the next `ready`
    must beat does not move, and the bands already notified are not reset."""
    repo, topic, session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path, repo_name="reopened", capture=idle_capture(ctx=40)
    )
    state = declare(repo=repo, topic=topic, value="done: release complete", mtime=950.0)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=900.0,
        session_identity=live_identity(topic=topic),
        stamp_path=sup.stamp_path,
    )
    for band in (50, 40):
        registry.add_notified_band(
            repo=str(repo), topic=topic, band=band, stamp_path=sup.stamp_path
        )
    round_before = registry.read_round_record(
        repo=str(repo), topic=topic, stamp_path=sup.stamp_path
    )

    with contextlib.redirect_stderr(_io.StringIO()):
        done_views = sup.tick(act=True)
    assert next(view for view in done_views if view.topic == topic).status == signals.STATE_DONE

    state.unlink()
    with contextlib.redirect_stderr(_io.StringIO()):
        reopened = sup.tick(act=True)

    row = next(view for view in reopened if view.topic == topic)
    assert row.status == "warned"
    assert (
        registry.read_round_record(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        == round_before
    )
    assert fake.paste_texts() == []


def test_scenario_an_archived_plan_moved_back_out_of_the_archive_is_supervised_again(*, tmp_path):
    """The daemon keys on the DIRECTORY alone, so moving a plan back to `plan/<topic>/`
    re-opens its track — provided it holds no `done` of its own."""
    repo, topic, _session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path, repo_name="unarchived", capture=idle_capture(ctx=40)
    )
    archive_plan(repo=repo, topic=topic)
    with contextlib.redirect_stderr(_io.StringIO()):
        archived = sup.tick(act=True)
    assert next(view for view in archived if view.topic == topic).status == signals.STATE_DONE
    assert fake.paste_texts() == []

    _ = shutil.move(str(repo / "plan" / "archive" / topic), str(repo / "plan" / topic))
    with contextlib.redirect_stderr(_io.StringIO()):
        reopened = sup.tick(act=True)

    row = next(view for view in reopened if view.topic == topic)
    assert row.status == "warned"
    assert row.archived_live is False
    assert len(fake.paste_texts()) == 1  # the wind-down its band had made due


def test_scenario_an_archived_plans_row_is_collected_once_its_session_is_gone(*, tmp_path):
    """Retention ends with the runtime, not with the archival: once the recorded session
    is gone the row leaves the table and its mapping is garbage-collected."""
    repo, topic, session, fake, sup = mapped_plan_track(
        tmp_path=tmp_path, repo_name="collected", capture=idle_capture(ctx=80)
    )
    archive_plan(repo=repo, topic=topic)
    with contextlib.redirect_stderr(_io.StringIO()):
        retained = sup.tick(act=True)
    assert [view.topic for view in retained] == [topic]
    assert [track.topic for track in registry.read_valid_mapping(store_path=sup.store_path)] == [
        topic
    ]

    assert fake.kill_session(session=session) is True
    with contextlib.redirect_stderr(_io.StringIO()):
        collected = sup.tick(act=True)

    assert collected == []
    assert registry.read_valid_mapping(store_path=sup.store_path) == []


def paired_done_worker(*, tmp_path, now):
    """A mapped worker track beside a LIVE attended supervisor seat, both idle.

    BOTH halves are in the Claude session registry, which is what makes the seat's own
    wind-down reachable: the threshold branch re-observes the pane immediately before
    pasting and settles for `settling` when it cannot prove the live session identity,
    so a seat with no registry entry is never acted on for reasons that have nothing to
    do with its worker being done.
    """
    repo, topic = make_plan(tmp_path=tmp_path, repo_name="done-pair")
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    worker_session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = signals.supervisor_entity_topic(topic=worker_session)
    sessions_dir = tmp_path / "pair" / "sessions"
    sessions_dir.mkdir(parents=True)
    write_session(sessions_dir=sessions_dir, pid=SESSION_PID, name=topic, cwd=repo)
    write_session(sessions_dir=sessions_dir, pid=201, name=supervisor_session, cwd=repo)
    fake = FakeTmux()
    fake.serve(session=worker_session, repo=repo, capture=idle_capture(ctx=40))
    fake.serve(session=supervisor_session, repo=repo, capture=idle_capture(ctx=40))
    fake.pane_pids = {100: worker_session, 101: supervisor_session}
    sup = make_supervisor(
        tmp_path=tmp_path / "pair",
        fake=fake,
        watch_repos=[str(repo)],
        own_pane="%7",
        now=now,
        sessions_dir=sessions_dir,
        ppid_of=lambda *, pid: {SESSION_PID: 100, 201: 101}.get(pid),
        starttime_of=lambda *, pid: {SESSION_PID: SESSION_PROC_START, 201: "pt"}.get(pid),
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session=worker_session),
        store_path=sup.store_path,
        added_at="2026-10-19T00:00:00Z",
    )
    write_fresh_supervisor_state(repo=repo, topic=supervisor_session)
    return sup, fake, repo, topic, supervisor_session


def test_the_supervisor_of_a_done_worker_is_neither_wound_down_nor_nudged(*, tmp_path):
    """The pair pass runs AFTER the cascade has already returned, so the cascade's own
    `done` leg cannot reach it: both `_supervisor_pair` calls have to be told the track
    is done too. The seat stays VISIBLE — it is simply not driven."""
    clock = {"t": 1000.0}
    sup, fake, repo, topic, supervisor_session = paired_done_worker(
        tmp_path=tmp_path, now=lambda: clock["t"]
    )
    _ = declare(repo=repo, topic=topic, value="done: release complete", mtime=950.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        views = sup.tick(act=True)
        clock["t"] += _supervisor_config.PAIR_STALL_AFTER + 1
        views = sup.tick(act=True)

    assert next(view for view in views if view.topic == topic).status == signals.STATE_DONE
    assert any(view.topic == supervisor_session for view in views)
    assert fake.paste_texts() == []
    assert not fake.has(method="keys")
    assert not fake.has(method="respawn")
