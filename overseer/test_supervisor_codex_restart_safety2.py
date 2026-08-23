"""Beside-tests for supervisor.py — codex restart safety2.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import _supervisor_view
import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import (
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    unsubmitted_resume_capture,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_fresh_respawn_dropped_enter_is_retried_next_tick_without_respawn(*, tmp_path):
    """The load-bearing self-heal: a restart whose resume Enter is DROPPED is retried on a
    later tick — re-sending Enter, NEVER a second respawn — and the round closes only once
    the box actually clears.

    Tick 1 models the dropped Enter (the fresh TUI shows the box holding the un-submitted
    resume for every post-respawn capture), so `_submit_prompt` returns False. Tick 2 the
    box clears on the retry's Enter. Asserts: (a) tick 1 keeps the marker + sets
    `resume_pending` and issues exactly ONE respawn; (b) tick 2 issues NO second respawn,
    re-sends Enter, and closes the round (marker + stamp gone, `resume_pending` cleared)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # Tick-1 frames: idle for the main read + the settle pair (reaches the restart branch),
    # then the un-submitted-resume box for every post-respawn capture (the last frame
    # repeats), so `_await_input_box` and every submit Enter see a box that never clears.
    idle = idle_capture(ctx=30)
    fake.serve(
        session=session, repo=repo, capture=[idle, idle, idle, unsubmitted_resume_capture(ctx=30)]
    )
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view1 = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view1.status == "restarting"
    assert len([c for c in fake.calls if c[0] == "respawn"]) == 1  # respawned exactly once
    assert marker.exists()  # the ready marker is KEPT — the round is NOT closed on a failed submit
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )

    # Tick 2: the box clears on the retry's Enter. Reset the capture frames + index.
    fake.panes[session] = [unsubmitted_resume_capture(ctx=30), idle_capture(ctx=95)]
    fake._cap_idx.pop(session, None)
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        view2 = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view2.status == "restarting"
    assert not fake.has(
        method="respawn"
    )  # NEVER a second respawn — the retry can never escalate to a kill
    assert any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)  # it re-sent Enter
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )


def test_restart_does_not_log_success_when_resume_unsubmitted(*, tmp_path):
    """A failed resume-submit must NOT log a clean "restarted" success — it marks
    `resume_pending`, alerts, and keeps the marker (the fresh Claude is up but idle with an
    un-run handoff; logging success would hide the stranding the maintainer reported)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    fake.paste_ok = False  # the paste fails → `_submit_prompt` returns False (a clean submit-fail)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    marker = arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    out = log.getvalue()
    assert f"restarted {repo}::{topic}" not in out  # NO clean success line
    assert "NOT submitted" in out  # the operator IS told the resume did not land
    assert marker.exists()  # marker kept so the next tick retries
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )


def test_submit_retry_never_kills_the_fresh_session(*, tmp_path):
    """The loop-safety property the Codex-#2 reasoning was protecting, now under the retry
    path: while a resume stays un-submitted the daemon retries the Enter every tick but
    NEVER respawns — so a still-valid `ready` can never re-fire `respawn-pane -k` and kill
    the live fresh Claude in a loop. The row stays a NEEDS-YOU report until it resumes."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # A box that NEVER clears (plain string) — the retry can never succeed here.
    fake.serve(session=session, repo=repo, capture=unsubmitted_resume_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    registry.set_resume_pending(
        repo=str(repo),
        topic=topic,
        session_identity=f"claude:{session}:{topic}",
        stamp_path=sup.stamp_path,
    )  # already respawned; resume pending

    for _ in range(3):
        with contextlib.redirect_stderr(_io.StringIO()):
            view = sup.evaluate(
                track=mapped_track(repo=repo, topic=topic, session=session), act=True
            )
        assert view.status == "restarting"
        assert view.note == _supervisor_view.RESUME_PENDING_NOTE
        assert supervisor.needs_attention(row=view)  # a stranded resume is a NEEDS-YOU row
        assert not fake.has(method="respawn")  # NEVER a respawn on the retry path
        assert (
            registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
            is True
        )
        assert (
            signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
        )  # marker kept


def test_idle_pane_with_resume_pending_closes_the_round_instead_of_respawning(*, tmp_path):
    """The sharp loop-safety case: with `resume_pending` set and a still-valid `ready`, an
    IDLE (empty-box) pane means the resume ALREADY submitted (a prior Enter, or the human) —
    so the retry branch closes the round rather than re-entering the `elif ready:` restart
    path and respawn-KILLING the fresh session. WITHOUT the retry interception this idle pane
    + valid ready would `_do_restart` → respawn: this is exactly the destructive loop the
    self-heal prevents."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=95)
    )  # empty box → the resume already landed
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    registry.set_resume_pending(
        repo=str(repo),
        topic=topic,
        session_identity=f"claude:{session}:{topic}",
        stamp_path=sup.stamp_path,
    )  # respawned; resume outstanding

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"
    assert not fake.has(
        method="respawn"
    )  # NEVER respawn-kill the fresh session — the round just closes
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )


def test_claude_restart_success_closes_the_round_and_issues_no_second_respawn(*, tmp_path):
    """Symmetric with the Codex success-leg guard (PR #1308 review): a Claude restart whose
    resume submits cleanly closes the round (marker + stamp gone) AND issues no second
    respawn on the next tick — else a stale `ready` would respawn-KILL the fresh session
    every tick, a destructive loop. Pins both runtimes' restart success legs symmetrically."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=30)
    )  # empty box → submit lands at once
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_RESTARTED
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is False
    )
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert not fake.has(method="respawn")  # no re-restart of the session we just resumed
