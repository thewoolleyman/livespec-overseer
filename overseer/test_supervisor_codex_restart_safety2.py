"""Beside-tests for supervisor.py — codex restart safety2.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import (
    adopt_sup,
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


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_fresh_respawn_dropped_enter_is_retried_next_tick_without_respawn(tmp_path):
    """The load-bearing self-heal: a restart whose resume Enter is DROPPED is retried on a
    later tick — re-sending Enter, NEVER a second respawn — and the round closes only once
    the box actually clears.

    Tick 1 models the dropped Enter (the fresh TUI shows the box holding the un-submitted
    resume for every post-respawn capture), so `_submit_prompt` returns False. Tick 2 the
    box clears on the retry's Enter. Asserts: (a) tick 1 keeps the marker + sets
    `resume_pending` and issues exactly ONE respawn; (b) tick 2 issues NO second respawn,
    re-sends Enter, and closes the round (marker + stamp gone, `resume_pending` cleared)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    # Tick-1 frames: idle for the main read + the settle pair (reaches the restart branch),
    # then the un-submitted-resume box for every post-respawn capture (the last frame
    # repeats), so `_await_input_box` and every submit Enter see a box that never clears.
    idle = idle_capture(ctx=30)
    fake.serve(session, repo, capture=[idle, idle, idle, unsubmitted_resume_capture(ctx=30)])
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view1 = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view1.status == "restarting"
    assert len([c for c in fake.calls if c[0] == "respawn"]) == 1  # respawned exactly once
    assert marker.exists()  # the ready marker is KEPT — the round is NOT closed on a failed submit
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is True

    # Tick 2: the box clears on the retry's Enter. Reset the capture frames + index.
    fake.panes[session] = [unsubmitted_resume_capture(ctx=30), idle_capture(ctx=95)]
    fake._cap_idx.pop(session, None)
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        view2 = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view2.status == "restarting"
    assert not fake.has(
        "respawn"
    )  # NEVER a second respawn — the retry can never escalate to a kill
    assert any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)  # it re-sent Enter
    assert not marker.exists()  # round closed only after the box cleared
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is False
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) is None


def test_restart_does_not_log_success_when_resume_unsubmitted(tmp_path):
    """A failed resume-submit must NOT log a clean "restarted" success — it marks
    `resume_pending`, alerts, and keeps the marker (the fresh Claude is up but idle with an
    un-run handoff; logging success would hide the stranding the maintainer reported)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    fake.paste_ok = False  # the paste fails → `_submit_prompt` returns False (a clean submit-fail)
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)

    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.evaluate(mapped_track(repo, topic, session), act=True)
    out = log.getvalue()
    assert f"restarted {repo}::{topic}" not in out  # NO clean success line
    assert "NOT submitted" in out  # the operator IS told the resume did not land
    assert marker.exists()  # marker kept so the next tick retries
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is True


def test_submit_retry_never_kills_the_fresh_session(tmp_path):
    """The loop-safety property the Codex-#2 reasoning was protecting, now under the retry
    path: while a resume stays un-submitted the daemon retries the Enter every tick but
    NEVER respawns — so a still-valid `ready` can never re-fire `respawn-pane -k` and kill
    the live fresh Claude in a loop. The row stays a NEEDS-YOU report until it resumes."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    # A box that NEVER clears (plain string) — the retry can never succeed here.
    fake.serve(session, repo, capture=unsubmitted_resume_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)
    registry.set_resume_pending(
        str(repo), topic, sup.stamp_path
    )  # already respawned; resume pending

    for _ in range(3):
        with contextlib.redirect_stderr(_io.StringIO()):
            view = sup.evaluate(mapped_track(repo, topic, session), act=True)
        assert view.status == "restarting"
        assert view.note == supervisor._RESUME_PENDING_NOTE
        assert supervisor.needs_attention(view)  # a stranded resume is a NEEDS-YOU row
        assert not fake.has("respawn")  # NEVER a respawn on the retry path
        assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is True
        assert signals.read_state(str(repo), topic).token == signals.STATE_READY  # marker kept


def test_idle_pane_with_resume_pending_closes_the_round_instead_of_respawning(tmp_path):
    """The sharp loop-safety case: with `resume_pending` set and a still-valid `ready`, an
    IDLE (empty-box) pane means the resume ALREADY submitted (a prior Enter, or the human) —
    so the retry branch closes the round rather than re-entering the `elif ready:` restart
    path and respawn-KILLING the fresh session. WITHOUT the retry interception this idle pane
    + valid ready would `_do_restart` → respawn: this is exactly the destructive loop the
    self-heal prevents."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=95))  # empty box → the resume already landed
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)
    registry.set_resume_pending(str(repo), topic, sup.stamp_path)  # respawned; resume outstanding

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"
    assert not fake.has("respawn")  # NEVER respawn-kill the fresh session — the round just closes
    assert signals.read_state(str(repo), topic) is None  # round closed (marker gone)
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is False


def test_claude_restart_success_closes_the_round_and_issues_no_second_respawn(tmp_path):
    """Symmetric with the Codex success-leg guard (PR #1308 review): a Claude restart whose
    resume submits cleanly closes the round (marker + stamp gone) AND issues no second
    respawn on the next tick — else a stale `ready` would respawn-KILL the fresh session
    every tick, a destructive loop. Pins both runtimes' restart success legs symmetrically."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))  # empty box → submit lands at once
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert signals.read_state(str(repo), topic) is None  # round closed
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is False
    fake.calls.clear()
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert not fake.has("respawn")  # no re-restart of the session we just resumed


# --------------------------------------------------------------------------- #
# R2 — Claude identity gate `name == topic` parity + stale-mapping re-point
# (2026-07-18). Generic reused tmux windows (livespec1…) are cycled across topics,
# so a window the store maps to topic A but now running topic B's Claude (same repo)
# passed the process+cwd gate and got A's wrap-up injected into B — then a `ready`
# respawn-KILLED B as A. The Codex gate was already pane-scoped (`name == topic`);
# this brings the Claude gate to parity and re-points the stale mapping.
# --------------------------------------------------------------------------- #


def test_claude_act_refuses_pane_whose_live_name_differs_from_topic(tmp_path):
    """A pane running a live Claude for a DIFFERENT topic (same repo) is NOT ours: the gate
    rejects it on the `name != topic` proof, so the track never injects into nor respawns
    it and renders `session-gone` — even with a valid `ready` that WOULD otherwise restart."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    # A genuinely-live Claude pane in this tmux session, cwd in the repo — but it is
    # topic BETA's session, not our track's ALPHA. (Process + cwd both pass; only the
    # name betrays it.)
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})  # empty registry → no live-outside-tmux
    sup._claude_names = {session: {"beta"}}  # the live Claude here belongs to topic `beta`
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)  # would restart if the gate passed

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"  # not ours → routed to session-gone, like a foreign pane
    assert not fake.has("respawn")  # never respawn-kill another topic's live Claude
    assert not fake.has("paste")  # never keystroke into it


def test_claude_gate_allows_pane_whose_live_name_matches_topic(tmp_path):
    """The parity check is POSITIVE-mismatch only: a matching `name == topic` (the normal
    case) still passes the gate and the track acts as before. Pairs with the refusal test so
    the check cannot be read as "reject unless proven" — it rejects only a proven mismatch."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    sup._claude_names = {session: {"alpha"}}  # the live Claude here IS our topic
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"  # name matches → ours → the `ready` restart fires
    assert fake.has("respawn")
