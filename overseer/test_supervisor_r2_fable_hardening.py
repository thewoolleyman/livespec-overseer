"""Beside-tests for supervisor.py — r2 claude identity, Fable-review hardening.

Split from `test_supervisor_r2_claude_identity.py` at the section banner that module
already carried, when the keyword-only conversion (`overseer-bg2.9`) re-wrapped its
call sites and took it past the 200-LLOC soft ceiling. Its sibling holds the R2
re-point behaviour proper — a stale tmux mapping being repointed, and that repoint
being idempotent. This module holds the five arms the 2026-07-18 Fable review asked
for, which probe the same gate from the ADVERSARIAL side: SF1 re-point flip-flop,
SF2 gate wiring through the production path, SF3 busy false-close, SF4 gate
keystroke, SF5 helper-Claude flap.

The doubles and builders live in `test_supervisor_fakes` / `test_supervisor_builders`;
this module holds only tests. ``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io
import os

import _supervisor_view
import pytest
import registry
import signals
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

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# Fable review hardening (2026-07-18): SF1 re-point flip-flop, SF2 gate wiring,
# SF3 busy false-close, SF4 gate keystroke, SF5 helper-Claude flap.
# --------------------------------------------------------------------------- #


def test_claude_name_gate_is_wired_end_to_end_through_the_registry(*, tmp_path):
    """SF2: the R2 name gate must reject a mismatched pane through the PRODUCTION wiring
    (registry → `_refresh_claude_status` → `claude_names_by_session` → gate), not only when a test
    hand-injects `claude_names_by_session`. A registry session named `beta` in the track's tmux
    session
    (topic `alpha`) → the wired gate rejects the pane → `session-gone`, no respawn."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))  # a live Claude pane
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    write_session(sessions_dir=sessions_dir, pid=100, name="beta", cwd=str(repo))  # NOT our topic
    ppid = {100: 50}
    fake.pane_pids[50] = session  # 100 → shell 50 → tmux `session`
    sup = adopt_sup(
        tmp_path=tmp_path, fake=fake, sessions_dir=sessions_dir, ppid=ppid, starttimes={100: "pt"}
    )
    with contextlib.redirect_stderr(_io.StringIO()):
        sup._refresh_claude_status()  # the WIRING under test
    # populated from the registry, not by hand
    assert sup.claude_names_by_session.get(session) == {"beta"}
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)  # would restart if the gate passed
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "session-gone"  # the WIRED name gate rejects the mismatched pane
    assert not fake.has(method="respawn")


def test_helper_claude_in_the_same_tmux_does_not_flap_the_track(*, tmp_path):
    """SF5: a HELPER Claude sharing the track's tmux session (a second window/split) must NOT
    shadow the track's own name and flap it to `session-gone`. With `claude_names_by_session` a
    SET, the
    track's topic being AMONG the live names is enough to keep the pane ours."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    # our topic present ALONGSIDE a helper
    sup.claude_names_by_session = {session: {"helper", "alpha"}}
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"  # NOT flapped to session-gone — the track is still ours
    assert fake.has(method="respawn")


def test_ambiguous_two_sessions_for_one_track_does_not_flip_flop_the_repoint(*, tmp_path):
    """SF1: when TWO live sessions carry the same (repo, topic) — dual-driving, or an
    R1-stranded pane plus a hand-started replacement — the re-point must NOT flip-flop the
    mapping between their tmux ids every tick (two store rewrites + two log lines forever).
    It skips the re-point while ambiguous and leaves the mapping untouched."""
    repo, topic = make_plan(tmp_path=tmp_path, topic="alpha")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake = FakeTmux()
    # TWO live sessions named `alpha`, in DIFFERENT tmux sessions `tmux-A` and `tmux-B`.
    write_session(sessions_dir=sessions_dir, pid=100, name="alpha", cwd=str(repo))
    write_session(sessions_dir=sessions_dir, pid=200, name="alpha", cwd=str(repo))
    ppid = {100: 50, 200: 60}
    fake.pane_pids = {50: "tmux-A", 60: "tmux-B"}
    starttimes = {100: "pt", 200: "pt"}
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes=starttimes,
        watch_repos=[str(repo)],
    )
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session="tmux-A"),
        store_path=sup.store_path,
        added_at="pre",
    )

    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.adopt_sessions()
        sup.adopt_sessions()  # a second tick must not flip it back
    rows = {
        (r.repo, r.topic): r.tmux for r in registry.read_valid_mapping(store_path=sup.store_path)
    }
    assert rows[(os.path.normpath(str(repo)), "alpha")] == "tmux-A"  # left untouched (ambiguous)
    assert "re-pointed" not in log.getvalue()  # no flip-flop, no log spam


def test_pending_resume_on_a_gate_reports_blocked_human_and_sends_no_enter(*, tmp_path):
    """SF4: a freshly-restarted pane that comes up on a picker (trust / update / bypass-perms
    confirm) must NOT be keystroked (blocker #6) — the retry reports `blocked:human`, sends no
    Enter, and keeps the round open so it resumes once the human clears the gate."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(
        session=session,
        repo=repo,
        capture="Do you want to proceed?\n❯ 1. Yes\n  2. No\n  Ctx: 90% left\n",
    )
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
    )
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "blocked:human"
    assert not any(c[0] == "keys" for c in fake.calls)  # NEVER keystroked the gate
    assert not fake.has(method="respawn")
    assert (
        signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    )  # round kept open
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )


def test_pending_retry_does_not_false_close_on_hook_busy_with_text_in_box(*, tmp_path):
    """SF3: a freshly-respawned session can be BUSY for reasons unrelated to the resume
    (SessionStart hooks) while the resume still sits UN-submitted in the box. The retry
    branches on the BOX STATE (text present → re-send Enter), never treating `busy` as
    'submitted' — else it would false-close the round and re-strand the session invisibly."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    # The box HOLDS the un-submitted resume text AND a hook spinner makes the pane busy.
    capture = "✻ (running SessionStart hooks… 1/2 · 3s)\n" + unsubmitted_resume_capture(ctx=90)
    fake.serve(session=session, repo=repo, capture=capture)
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
    )
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)
    assert view.status == "restarting"
    assert view.note == _supervisor_view.RESUME_PENDING_NOTE  # still pending, NOT falsely closed
    assert (
        signals.read_state(repo=str(repo), topic=topic).token == signals.STATE_READY
    )  # marker KEPT
    assert (
        registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path) is True
    )
    assert any(c[0] == "keys" and c[2] == "Enter" for c in fake.calls)  # it DID re-send Enter
    assert not fake.has(method="respawn")
