"""Beside-tests for supervisor.py — r2 claude identity.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import os

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
    write_session,
)
from test_supervisor_fakes import (
    FakeTmux,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_stale_tmux_mapping_is_repointed_when_topic_session_moves(tmp_path):
    """When a topic's live named session resolves to a DIFFERENT tmux session than the store
    records (a generic window reused for another topic; the session moved), adoption
    RE-POINTS the mapping to the current tmux within one tick rather than freezing the stale
    binding. The re-pointed store then drives acts at the RIGHT pane."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    ppid: dict[int, int] = {}
    starttimes: dict[int, str] = {}
    # A live named session for `alpha` whose pid walks up to tmux session `new-tmux`.
    write_session(sessions_dir, 100, name="alpha", cwd=str(repo))
    starttimes[100] = "pt"
    shell = 101
    ppid[100] = shell
    fake.pane_pids[shell] = "new-tmux"
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, starttimes, watch_repos=[str(repo)])
    # The store maps `alpha` to a STALE tmux session (`old-tmux`) — where it used to run.
    registry.append_mapping(mapped_track(repo, topic, "old-tmux"), sup.store_path, added_at="pre")

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.adopt_sessions()

    rows = {(r.repo, r.topic): r.tmux for r in registry.read_mapping(sup.store_path)}
    assert (
        rows[(os.path.normpath(str(repo)), "alpha")] == "new-tmux"
    )  # re-pointed to the live session


def test_repoint_is_idempotent_when_the_mapping_already_matches(tmp_path):
    """A steady-state tick where the live session's tmux already equals the stored mapping
    must NOT rewrite the store (no churn) and must NOT re-adopt (no duplicate row)."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    write_session(sessions_dir, 100, name="alpha", cwd=str(repo))
    ppid = {100: 101}
    fake.pane_pids[101] = "the-tmux"
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, {100: "pt"}, watch_repos=[str(repo)])
    registry.append_mapping(mapped_track(repo, topic, "the-tmux"), sup.store_path, added_at="pre")

    assert registry.repoint_tmux(str(repo), topic, "the-tmux", sup.store_path) is False  # no-op
    with contextlib.redirect_stderr(_io.StringIO()):
        adopted = sup.adopt_sessions()
    assert adopted == []  # already mapped, tmux unchanged → neither re-adopted nor re-pointed
    rows = registry.read_mapping(sup.store_path)
    assert len([r for r in rows if r.topic == "alpha"]) == 1  # exactly one row, no duplicate
    assert rows[0].tmux == "the-tmux"


# --------------------------------------------------------------------------- #
# Fable review hardening (2026-07-18): SF1 re-point flip-flop, SF2 gate wiring,
# SF3 busy false-close, SF4 gate keystroke, SF5 helper-Claude flap.
# --------------------------------------------------------------------------- #


def test_claude_name_gate_is_wired_end_to_end_through_the_registry(tmp_path):
    """SF2: the R2 name gate must reject a mismatched pane through the PRODUCTION wiring
    (registry → `_refresh_claude_status` → `_claude_names` → gate), not only when a test
    hand-injects `_claude_names`. A registry session named `beta` in the track's tmux session
    (topic `alpha`) → the wired gate rejects the pane → `session-gone`, no respawn."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))  # a live Claude pane
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir, 100, name="beta", cwd=str(repo))  # NOT our topic
    ppid = {100: 50}
    fake.pane_pids[50] = session  # 100 → shell 50 → tmux `session`
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, {100: "pt"})
    with contextlib.redirect_stderr(_io.StringIO()):
        sup._refresh_claude_status()  # the WIRING under test
    assert sup._claude_names.get(session) == {"beta"}  # populated from the registry, not by hand
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)  # would restart if the gate passed
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"  # the WIRED name gate rejects the mismatched pane
    assert not fake.has("respawn")


def test_helper_claude_in_the_same_tmux_does_not_flap_the_track(tmp_path):
    """SF5: a HELPER Claude sharing the track's tmux session (a second window/split) must NOT
    shadow the track's own name and flap it to `session-gone`. With `_claude_names` a SET, the
    track's topic being AMONG the live names is enough to keep the pane ours."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    sup._claude_names = {session: {"helper", "alpha"}}  # our topic present ALONGSIDE a helper
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"  # NOT flapped to session-gone — the track is still ours
    assert fake.has("respawn")


def test_ambiguous_two_sessions_for_one_track_does_not_flip_flop_the_repoint(tmp_path):
    """SF1: when TWO live sessions carry the same (repo, topic) — dual-driving, or an
    R1-stranded pane plus a hand-started replacement — the re-point must NOT flip-flop the
    mapping between their tmux ids every tick (two store rewrites + two log lines forever).
    It skips the re-point while ambiguous and leaves the mapping untouched."""
    repo, topic = make_plan(tmp_path, topic="alpha")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    # TWO live sessions named `alpha`, in DIFFERENT tmux sessions `tmux-A` and `tmux-B`.
    write_session(sessions_dir, 100, name="alpha", cwd=str(repo))
    write_session(sessions_dir, 200, name="alpha", cwd=str(repo))
    ppid = {100: 50, 200: 60}
    fake.pane_pids = {50: "tmux-A", 60: "tmux-B"}
    starttimes = {100: "pt", 200: "pt"}
    sup = adopt_sup(tmp_path, fake, sessions_dir, ppid, starttimes, watch_repos=[str(repo)])
    registry.append_mapping(mapped_track(repo, topic, "tmux-A"), sup.store_path, added_at="pre")

    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.adopt_sessions()
        sup.adopt_sessions()  # a second tick must not flip it back
    rows = {(r.repo, r.topic): r.tmux for r in registry.read_mapping(sup.store_path)}
    assert rows[(os.path.normpath(str(repo)), "alpha")] == "tmux-A"  # left untouched (ambiguous)
    assert "re-pointed" not in log.getvalue()  # no flip-flop, no log spam


def test_pending_resume_on_a_gate_reports_blocked_human_and_sends_no_enter(tmp_path):
    """SF4: a freshly-restarted pane that comes up on a picker (trust / update / bypass-perms
    confirm) must NOT be keystroked (blocker #6) — the retry reports `blocked:human`, sends no
    Enter, and keeps the round open so it resumes once the human clears the gate."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(
        session, repo, capture="Do you want to proceed?\n❯ 1. Yes\n  2. No\n  Ctx: 90% left\n"
    )
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)
    registry.set_resume_pending(str(repo), topic, sup.stamp_path)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    assert not any(c[0] == "keys" for c in fake.calls)  # NEVER keystroked the gate
    assert not fake.has("respawn")
    assert signals.read_state(str(repo), topic).token == signals.STATE_READY  # round kept open
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is True


def test_pending_retry_does_not_false_close_on_hook_busy_with_text_in_box(tmp_path):
    """SF3: a freshly-respawned session can be BUSY for reasons unrelated to the resume
    (SessionStart hooks) while the resume still sits UN-submitted in the box. The retry
    branches on the BOX STATE (text present → re-send Enter), never treating `busy` as
    'submitted' — else it would false-close the round and re-strand the session invisibly."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    # The box HOLDS the un-submitted resume text AND a hook spinner makes the pane busy.
    capture = "✻ (running SessionStart hooks… 1/2 · 3s)\n" + unsubmitted_resume_capture(ctx=90)
    fake.serve(session, repo, capture=capture)
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    arm_ready_marker(repo, topic, mtime=1001.0)
    registry.set_resume_pending(str(repo), topic, sup.stamp_path)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"
    assert view.note == supervisor._RESUME_PENDING_NOTE  # still pending, NOT falsely closed
    assert signals.read_state(str(repo), topic).token == signals.STATE_READY  # marker KEPT
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is True
    assert any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)  # it DID re-send Enter
    assert not fake.has("respawn")
