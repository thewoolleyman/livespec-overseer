"""Beside-tests for supervisor.py — voiding stale blocked2.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import codex_sessions
import pytest
import registry
import supervisor
from test_supervisor_builders import (
    codex_idle_capture,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    wrapup_count,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_supervisor_session_without_a_pane_is_not_running(*, tmp_path):
    """A tmux session that cannot resolve to a pane is not live process evidence.

    `_supervisor_running` can answer False three independent ways: the session does not
    exist, it resolves to NO PANE, or its pane process is neither Claude-like nor a
    Codex pane joined to a live rollout. This test owns the MIDDLE leg, so the
    supervisor session is otherwise a perfectly live supervisor — served with a
    Claude-like `node` pane whose cwd is inside the repo — and the ONLY thing making it
    not-running is that its pane id does not resolve.

    That setup is load-bearing. An earlier version added the supervisor session to
    `fake.sessions` WITHOUT serving it, so `pane_current_command` returned None and the
    THIRD leg answered False on its own; the paneless override then changed nothing and
    the test passed with it neutered — it asserted the message but proved nothing about
    panes. Serving the session makes the paneless declaration the only cause, so
    dropping it now flips `running` to True, takes the early return, emits no alert, and
    reddens the second assertion.

    The session is declared paneless through `FakeTmux.no_pane_sessions` rather than by
    subclassing the double to override `pane_id` — the double's own seam idiom, which is
    also what keeps this out of `check-no-inheritance`.
    """
    repo, topic = make_plan(tmp_path=tmp_path)
    (repo / "plan" / topic / "supervisor-handoff.md").write_text("supervise this\n")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = f"{session}-supervisor"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    fake.serve(session=supervisor_session, repo=repo, capture=idle_capture(ctx=73))
    fake.no_pane_sessions.add(supervisor_session)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle-with-context-left"
    assert "supervisor handoff exists" in err.getvalue()


def test_codex_supervisor_process_counts_as_running(*, tmp_path):
    """A Codex supervisor is running only when pane evidence and live rollout evidence
    agree on the supervisor tmux session and repository."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    supervisor_session = f"{session}-supervisor"
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    fake.serve(session=supervisor_session, repo=repo, capture=codex_idle_capture(ctx=73), cmd="bun")
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.live_codex = {
        (supervisor_session, f"{topic}-supervisor"): codex_sessions.CodexSession(
            pid=123,
            name=f"{topic}-supervisor",
            cwd=str(repo),
            session_id="00000000-0000-0000-0000-000000000000",
        )
    }
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle-with-context-left"
    assert "supervision is running but has no durable prompt" in err.getvalue()


def test_escalates_one_paste_per_band_as_ctx_drops(*, tmp_path):
    """Part 2: warn ONCE at the threshold, then once more each time remaining
    crosses a lower 10%-band (40, 30, 20, 10) — each band at most once. Feeding
    ctx exactly at each band yields exactly one NEW wrap-up paste per band; a
    re-tick at the same low ctx (all bands already notified) adds none."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo)
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)  # warn_percent = the default (50)
    track = mapped_track(repo=repo, topic=topic, session=session)
    counts = []
    for ctx in (45, 40, 30, 20, 10):
        fake.panes[session] = idle_capture(ctx=ctx)
        sup.evaluate(track=track, act=True)
        counts.append(wrapup_count(fake=fake))
    assert counts == [1, 2, 3, 4, 5]  # one new paste per band crossed
    # Same low ctx again: every band already notified → no further paste.
    fake.panes[session] = idle_capture(ctx=10)
    sup.evaluate(track=track, act=True)
    assert wrapup_count(fake=fake) == 5


def test_multi_band_drop_coalesces_to_one_paste_marks_all(*, tmp_path):
    """Part 2: several bands crossed in ONE tick coalesce into a SINGLE wrap-up
    paste, yet ALL crossed bands are marked notified so none re-fires; a later,
    lower tick fires only the newly-crossed band."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=18)
    )  # crosses 45,40,30,20 at once
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, warn_percent=45
    )  # explicit threshold: decouple from the default
    track = mapped_track(repo=repo, topic=topic, session=session)
    view = sup.evaluate(track=track, act=True)
    assert wrapup_count(fake=fake) == 1  # coalesced into ONE message
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    ) == {45, 40, 30, 20}
    assert view.status == "danger"  # 18 <= DANGER_CTX_REMAINING (20)
    # A still-lower tick fires only the new band (10), once.
    fake.panes[session] = idle_capture(ctx=8)
    sup.evaluate(track=track, act=True)
    assert wrapup_count(fake=fake) == 2
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    ) == {
        45,
        40,
        30,
        20,
        10,
    }


def test_bands_are_durable_across_daemon_restart(*, tmp_path):
    """Part 2 durability: a band recorded in the sidecar is NOT re-injected after a
    daemon RESTART — simulated by a FRESH Supervisor (empty in-memory state) built
    on the SAME stamp_path. Escalation state lives in the durable sidecar."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    stamp_path = str(tmp_path / "stamps.json")
    store_path = str(tmp_path / "map.jsonl")
    track = mapped_track(repo=repo, topic=topic, session=session)

    fake1 = FakeTmux()
    fake1.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup1 = supervisor.Supervisor(
        tmux=fake1,
        store_path=store_path,
        stamp_path=stamp_path,
        status_path=str(tmp_path / "status-1.json"),
        out=_io.StringIO(),
        now=lambda: 1000.0,
        sleep=lambda _s: None,
        warn_percent=45,  # explicit threshold: decouple from the default
    )
    sup1.claude_status_by_session = {session: "idle"}
    sup1.evaluate(track=track, act=True)
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=stamp_path)
    ) == {45, 40}
    assert fake1.has(method="paste")

    # "Restart": a brand-new Supervisor on the SAME sidecar, same ctx.
    fake2 = FakeTmux()
    fake2.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup2 = supervisor.Supervisor(
        tmux=fake2,
        store_path=store_path,
        stamp_path=stamp_path,
        status_path=str(tmp_path / "status-2.json"),
        out=_io.StringIO(),
        now=lambda: 2000.0,
        sleep=lambda _s: None,
        warn_percent=45,  # explicit threshold: decouple from the default
    )
    sup2.claude_status_by_session = {session: "idle"}
    sup2.evaluate(track=track, act=True)
    assert not fake2.has(method="paste")  # bands 45+40 already notified → no re-spam


def test_cleared_round_re_warns_all_bands(*, tmp_path):
    """Part 2: clearing the injection stamp (as a restart does) resets BOTH the
    round timestamp and the notified bands, so a fresh round re-warns from the top
    band again."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    sup = make_supervisor(
        tmp_path=tmp_path, fake=fake, warn_percent=45
    )  # explicit threshold: decouple from the default
    track = mapped_track(repo=repo, topic=topic, session=session)
    sup.evaluate(track=track, act=True)
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    ) == {45, 40}
    # Clear the round (mirrors _void_ready_marker / restart) → bands reset.
    registry.clear_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert (
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) == []
    )
    sup.evaluate(track=track, act=True)  # fresh round → re-warns the crossed bands again
    assert wrapup_count(fake=fake) == 2  # a second wrap-up in the new round
    assert set(
        registry.read_notified_bands(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    ) == {45, 40}


def test_danger_surfaces_below_danger_line(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=15)
    )  # <= DANGER, no ready marker
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "danger"
