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
    busy_capture,
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


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_failed_paste_clears_stamp_and_does_not_advance(tmp_path):
    """B5: if the wrap-up paste fails, the injection stamp is CLEARED and count is
    NOT advanced, so the next tick retries rather than the round being counted as
    open with an un-delivered wrap-up."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=40))
    fake.paste_ok = False  # the bracketed paste fails
    sup = make_supervisor(tmp_path, fake)
    sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) is None
    # Next tick retries (writes the stamp again + attempts paste again).
    sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert len([c for c in fake.calls if c[0] == "paste"]) == 2


def test_ctx_unknown_never_injects(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=None))  # idle but NO Ctx line → unknown
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "idle"
    assert view.ctx is None
    assert not fake.has("paste")


def test_idle_above_threshold_nudges_to_keep_going_only_after_an_hour(tmp_path):
    """A session idle at an empty prompt with context ABOVE the threshold and no declaration
    is nudged ONCE to keep going — but ONLY after it has been continuously idle for at least
    `IDLE_NUDGE_AFTER` (maintainer 2026-07-18: nudging a briefly-idle session interrupts
    active work). Below the floor it reads `idle-with-context-left` but is NOT keystroked; a
    tick past the floor nudges once, and a further idle tick does NOT re-nudge."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))  # well above threshold
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path, fake, now=lambda: clock["t"])
    sup._claude_status = {session: "idle"}
    track = mapped_track(repo, topic, session)

    # First idle tick: descriptive status, but NOT yet nudged (idle < 1 hour).
    view = sup.evaluate(track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake) == 0  # too soon — must be idle ≥ 1 hour first
    assert signals.read_state(str(repo), topic) is None  # no marker written yet

    # Past the 1-hour floor → nudged ONCE, marker written.
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    view = sup.evaluate(track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake) == 1  # nudged once
    assert wrapup_count(fake) == 0  # a keep-going nudge, NOT a wind-down wrap-up
    state = signals.read_state(str(repo), topic)
    assert state is not None and state.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT

    # Still idle with the marker present → single prompt: NOT re-nudged.
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    view = sup.evaluate(track, act=True)
    assert view.status == "idle-with-context-left"
    assert nudge_count(fake) == 1


def test_nudge_re_arms_after_the_session_takes_a_turn(tmp_path):
    """Single prompt per EPISODE: after a nudge, the session going non-idle (busy) clears the
    marker AND resets the idle clock, so idling with context left AGAIN re-nudges — but again
    only after a fresh 1-hour idle spell (brief idle after a turn is not nudged)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path, fake, now=lambda: clock["t"])
    sup._claude_status = {session: "idle"}
    track = mapped_track(repo, topic, session)

    sup.evaluate(track, act=True)  # idle_since stamped
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake) == 1

    # The session takes a turn (Claude busy) → marker cleared AND the idle clock reset.
    sup._claude_status = {session: "busy"}
    assert sup.evaluate(track, act=True).status == "working"
    assert signals.read_state(str(repo), topic) is None  # marker gone

    # Idle again with context left but only BRIEFLY → not yet re-nudged (fresh 1h clock).
    sup._claude_status = {session: "idle"}
    assert sup.evaluate(track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake) == 1  # the new episode has not reached the floor

    # Past a fresh hour → a SECOND nudge (a new episode).
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    assert sup.evaluate(track, act=True).status == "idle-with-context-left"
    assert nudge_count(fake) == 2


def test_claude_waiting_is_not_nudged(tmp_path):
    """A session Claude reports as `waiting` (at a gate/prompt for the human) is NOT nudged
    even above threshold — it is a blocking question for the human, not free to continue."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake)
    sup._claude_status = {session: "waiting"}
    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "idle"
    assert nudge_count(fake) == 0


def test_nudge_never_overwrites_a_session_declaration(tmp_path):
    """The daemon writes `idle-with-context-left` ONLY when the file is empty — a session
    that declared `blocked` (the Codex waiting-on-human-in-prose escape) is never nudged
    and its declaration is never clobbered."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))
    sup = make_supervisor(tmp_path, fake)
    sup._claude_status = {session: "idle"}
    declare(repo, topic, "blocked: waiting on a human decision (asked in prose)")
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    assert nudge_count(fake) == 0
    state = signals.read_state(str(repo), topic)  # the declaration survived untouched
    assert state is not None and state.token == signals.STATE_BLOCKED


# --------------------------------------------------------------------------- #
# Voiding a stale `blocked:` declaration. A GENERATING session is, by observation,
# not waiting on a human — so a `blocked:` it has outlived is provably false, and a
# dead reason must not ride a `working` row nor fire a false `blocked:human` alert
# when the session next goes idle. Found live 2026-07-16: a fresh overseer-rewrite
# session rendered `working (awaiting maintainer next-step decision — Codex…)` — the
# PREVIOUS session's declaration, inherited because the pane was replaced out-of-band
# (so `_do_restart`'s `_clear_state` never ran).
# --------------------------------------------------------------------------- #


def test_stale_blocked_is_voided_when_the_session_resumes_generating(tmp_path):
    """Past the grace + a real generation spinner ⇒ the declaration is provably dead."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=busy_capture())  # a real spinner: generating
    sup = make_supervisor(tmp_path, fake)
    declare(repo, topic, "blocked: a reason from a session that has moved on", mtime=800.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    assert view.note is None  # the dead reason no longer rides the row
    assert signals.read_state(str(repo), topic) is None  # voided


def test_fresh_blocked_survives_the_declaring_turns_own_busy_tail(tmp_path):
    """RB1, for `blocked` as for `ready`: the declaring turn's final text keeps streaming
    for 10-60s AFTER the write, so a YOUNG declaration must survive a busy tick — else
    every legitimate declaration is destroyed before the pane ever goes idle."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=busy_capture())
    sup = make_supervisor(tmp_path, fake)
    declare(repo, topic, "blocked: I need your call", mtime=1001.0)  # younger than the grace
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    state = signals.read_state(str(repo), topic)
    assert state is not None and state.token == signals.STATE_BLOCKED  # survived


def test_blocked_with_only_a_background_shell_is_never_voided(tmp_path):
    """The counter-case that bounds the rule. A session busy ONLY via a live
    `Bash(run_in_background)` command (Claude `shell`) is AT ITS PROMPT — it can be
    genuinely waiting on a human while a build runs, so its declaration is NOT provably
    stale and must survive however old it is. Only GENERATING voids."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))  # no spinner
    sup = make_supervisor(tmp_path, fake)
    sup._claude_status = {session: "shell"}  # busy via a background command only
    declare(repo, topic, "blocked: need your call", mtime=800.0)  # old, but NOT stale
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "working"
    state = signals.read_state(str(repo), topic)
    assert state is not None and state.token == signals.STATE_BLOCKED  # survived
