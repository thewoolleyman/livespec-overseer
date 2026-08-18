"""Beside-tests for supervisor.py — warned stamp written.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import _supervisor_config
import pytest
import registry
import signals
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    wrapup_count,
)
from test_supervisor_fakes import (
    FakeTmux,
)

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_failed_paste_clears_stamp_and_does_not_advance(*, tmp_path):
    """B5: if the wrap-up paste fails, the injection stamp is CLEARED and count is
    NOT advanced, so the next tick retries rather than the round being counted as
    open with an un-delivered wrap-up."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    fake.paste_ok = False  # the bracketed paste fails
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert (
        registry.read_injection_stamp(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
        is None
    )
    # Next tick retries (writes the stamp again + attempts paste again).
    sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert len([c for c in fake.calls if c[0] == "paste"]) == 2


def test_ctx_unknown_never_injects(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session, repo=repo, capture=idle_capture(ctx=None)
    )  # idle but NO Ctx line → unknown
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle"
    assert view.ctx is None
    assert not fake.has(method="paste")


def test_condition_episode_continues_inside_the_gap(*, tmp_path):
    import _supervisor_observe
    import _supervisor_records

    episode = _supervisor_records.ConditionEpisode(since=100.0, last_seen=120.0)
    _supervisor_observe.advance_condition(episode=episode, condition_now=True, now=130.0)
    assert episode.since == 100.0
    assert episode.last_seen == 130.0


def test_ctx_stale_projection_is_read_only_when_listing(*, tmp_path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=40))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=None))
    clock["t"] += 3600.0 + 1.0
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track=track, act=False)
    assert view.status == "ctx-stale"
    assert view.ctx is None
    assert "overseer[SURFACE]" not in err.getvalue()


def test_stale_ctx_age_helper_returns_none_before_the_window(*, tmp_path):
    import _supervisor_observe
    import _supervisor_records

    state = _supervisor_records.InjectState(last_ctx_seen=100.0)
    assert (
        _supervisor_observe.observed_stale_ctx_age(
            state=state, current=None, eff_ctx=None, now=200.0
        )
        is None
    )


def test_idle_above_threshold_nudges_to_keep_going_only_after_an_hour(*, tmp_path):
    """A session idle at an empty prompt with context ABOVE the threshold and no declaration
    is nudged ONCE to keep going — but ONLY after it has been continuously idle for at least
    `IDLE_NUDGE_AFTER` (maintainer 2026-07-18: nudging a briefly-idle session interrupts
    active work). Below the floor it reads `idle-with-context-left` but is NOT keystroked; a
    tick past the floor nudges once, and a further idle tick does NOT re-nudge."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))  # well above threshold
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    # First idle tick: descriptive status, but NOT yet nudged (idle < 1 hour).
    view = sup.evaluate(track=track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 0  # too soon — must be idle ≥ 1 hour first
    assert signals.read_state(repo=str(repo), topic=topic) is None  # no marker written yet

    # Past the 1-hour floor → nudged ONCE, marker written.
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    view = sup.evaluate(track=track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1  # nudged once
    assert wrapup_count(fake=fake) == 0  # a keep-going nudge, NOT a wind-down wrap-up
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT

    # Still idle with the marker present → single prompt: NOT re-nudged.
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    view = sup.evaluate(track=track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1


def test_nudge_re_arms_after_the_session_takes_a_turn(*, tmp_path):
    """Single prompt per EPISODE: after a nudge, the session going non-idle (busy) clears the
    marker AND resets the idle clock, so idling with context left AGAIN re-nudges — but again
    only after a fresh 1-hour idle spell (brief idle after a turn is not nudged)."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo=repo, topic=topic, session=session)

    sup.evaluate(track=track, act=True)  # idle_since stamped
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1

    # The session takes a turn (Claude busy) → marker cleared AND the idle clock reset.
    sup.claude_status_by_session = {session: "busy"}
    assert sup.evaluate(track=track, act=True).status == "working"
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_NUDGE_CLEARED

    # Idle again with context left but only BRIEFLY → not yet re-nudged (fresh 1h clock).
    sup.claude_status_by_session = {session: "idle"}
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1  # the new episode has not reached the floor

    # Past a fresh hour → a SECOND nudge (a new episode).
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 2


def test_claude_waiting_is_not_nudged(*, tmp_path):
    """A session Claude reports as `waiting` (at a gate/prompt for the human) is NOT nudged
    even above threshold — it is a blocking question for the human, not free to continue."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "waiting"}
    view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "idle"
    assert nudge_count(fake=fake) == 0


def test_nudge_never_overwrites_a_session_declaration(*, tmp_path):
    """The daemon writes `idle-with-context-left` ONLY when the file is empty — a session
    that declared `blocked` (the Codex waiting-on-human-in-prose escape) is never nudged
    and its declaration is never clobbered."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_status_by_session = {session: "idle"}
    declare(repo=repo, topic=topic, value="blocked: waiting on a human decision (asked in prose)")
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "blocked:human"
    assert nudge_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)  # the declaration survived untouched
    assert state is not None and state.token == signals.STATE_BLOCKED


@pytest.mark.parametrize(
    "stale_declaration",
    [
        signals.STATE_WINDING_DOWN,
        signals.STATE_READY,
    ],
)
def test_session_cleared_stale_wind_down_declaration_re_enters_nudge_path(
    *, tmp_path, stale_declaration
):
    """Once v019's session-side expiry clears the stale token, the daemon sees no
    session declaration and the next long idle-above-threshold episode is nudged."""
    repo, topic = make_plan(tmp_path=tmp_path, repo_name="cleared", topic=stale_declaration)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    state_path = declare(repo=repo, topic=topic, value=stale_declaration, mtime=1.0)

    state_path.unlink()
    track = mapped_track(repo=repo, topic=topic, session=session)
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track=track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake=fake) == 1
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT


@pytest.mark.parametrize(
    ("stale_declaration", "uncleared_status"),
    [
        (signals.STATE_WINDING_DOWN, "idle"),
        (signals.STATE_READY, "ready-uncertifiable"),
    ],
)
def test_uncleared_stale_wind_down_declaration_suppresses_nudge(
    *, tmp_path, stale_declaration, uncleared_status
):
    """A stale declaration the session has not cleared is still standing state. The
    daemon deliberately does not reinterpret it as absent or auto-clear it."""
    repo, topic = make_plan(tmp_path=tmp_path, repo_name="uncleared", topic=stale_declaration)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path=tmp_path, fake=fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    declare(repo=repo, topic=topic, value=stale_declaration, mtime=1.0)
    track = mapped_track(repo=repo, topic=topic, session=session)

    with contextlib.redirect_stderr(_io.StringIO()):
        _ = sup.evaluate(track=track, act=True)
        clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
        view = sup.evaluate(track=track, act=True)

    assert view.status == uncleared_status
    assert nudge_count(fake=fake) == 0
    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None and state.token == stale_declaration
