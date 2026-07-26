"""Beside-tests for supervisor.py — fail soft marker.

Split from `test_supervisor.py`, which carried the whole daemon surface at 3010 LLOC
after its shared helpers were extracted — still more than twelve times the 250-LLOC
hard ceiling. The doubles and builders live in `test_supervisor_fakes` /
`test_supervisor_builders`; this module holds only tests.

``import supervisor`` resolves via conftest.py.
"""

import contextlib
import io as _io

import _supervisor_config
import _supervisor_records
import pytest
import registry
import signals
import supervisor
from test_supervisor_builders import (
    adopt_sup,
    arm_ready_marker,
    idle_capture,
    key_for,
    make_plan,
    make_supervisor,
    mapped_track,
    nudge_count,
    on_respawn,
    undeletable_state_file,
)
from test_supervisor_fakes import (
    FakeTmux,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_clear_state_logs_an_undeletable_marker_and_still_closes_the_round(tmp_path):
    """`_clear_state` must not raise when the marker cannot be deleted: it logs the
    failure and still performs the REST of the clear (stamp + in-memory round), so a
    single unlink failure cannot abort the tick mid-restart."""
    repo, topic = make_plan(tmp_path)
    undeletable_state_file(repo, topic)
    sup = make_supervisor(tmp_path, FakeTmux())
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    key = key_for(repo, topic)
    sup.inject[key] = _supervisor_records.InjectState(last_ctx=30)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup._clear_state(mapped_track(repo, topic, "sesA"))

    assert "could not delete state file" in err.getvalue()
    assert topic in err.getvalue()
    # The round still closed: the durable stamp is gone and the in-memory state popped.
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) is None
    assert key not in sup.inject


def test_unreadable_ready_marker_leaves_the_ready_flag_as_is(tmp_path):
    """`_void_if_stale` voids a declaration it can prove is stale. An UNREADABLE marker
    proves nothing, so the flag comes back untouched and nothing is cleared —
    `ready_valid` is the gate that already refused to trust it."""
    repo, topic = make_plan(tmp_path)
    sup = make_supervisor(tmp_path, FakeTmux())
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    track = mapped_track(repo, topic, "sesA")

    assert sup._void_if_stale(track, ready=True) is True  # no state file → unreadable
    # and the round was NOT closed behind the daemon's back
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) == 1000.0


def test_void_stale_blocked_keeps_the_reason_when_the_marker_no_longer_declares_one(tmp_path):
    """`_void_stale_blocked` only retires a `blocked:` it can still SEE on disk. An
    unreadable file, or one that now declares something else, leaves the caller's reason
    untouched — voiding on a read it could not make would destroy a live declaration."""
    repo, topic = make_plan(tmp_path)
    sup = make_supervisor(tmp_path, FakeTmux())
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    track = mapped_track(repo, topic, "sesA")
    blocked = "blocked: waiting on the schema call"

    # (a) no state file at all → unreadable
    assert sup._void_stale_blocked(track, blocked, generating=True) == blocked
    # (b) the file exists but the session has since declared `ready` — not a block anymore
    arm_ready_marker(repo, topic, mtime=1.0)  # far past the grace, so only the token gates
    assert sup._void_stale_blocked(track, blocked, generating=True) == blocked
    # Neither path ran `_clear_state`, so the round is intact.
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) == 1000.0


def test_idle_nudge_marker_write_failure_is_logged_not_raised(tmp_path):
    """The daemon-owned `idle-with-context-left` marker lives under a per-topic dir. When
    that dir cannot be created the write is logged and skipped — never raised — and no
    marker is left behind, so the next idle tick simply re-nudges."""
    repo, topic = make_plan(tmp_path)
    marker_dir = signals.state_path(str(repo), topic).parent
    marker_dir.parent.mkdir(parents=True, exist_ok=True)
    marker_dir.write_text("a FILE where the marker dir belongs\n", encoding="utf-8")
    sup = make_supervisor(tmp_path, FakeTmux())
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup._write_idle_nudge_state(mapped_track(repo, topic, "sesA"))

    assert "could not write idle-nudge marker" in err.getvalue()
    assert signals.read_state(str(repo), topic) is None  # nothing was written


def test_failed_nudge_alerts_and_writes_no_marker_so_it_retries(tmp_path):
    """The nudge marker is written only AFTER the paste lands. A failed paste must
    ALERT (naming the tmux coordinate) and leave the episode unmarked, so the next tick
    re-nudges rather than silently recording a keep-going prompt that never arrived."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=73))  # idle, well above threshold
    fake.paste_ok = False  # the bracketed paste does not land
    clock = {"t": 1000.0}
    sup = make_supervisor(tmp_path, fake, now=lambda: clock["t"])
    sup.claude_status_by_session = {session: "idle"}
    track = mapped_track(repo, topic, session)

    sup.evaluate(track, act=True)  # stamps idle_since
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    err = _io.StringIO()
    with contextlib.redirect_stderr(err):
        view = sup.evaluate(track, act=True)

    assert view.status == "idle-with-context-left"
    assert "idle-with-context-left nudge FAILED" in err.getvalue()
    assert session in err.getvalue()  # the alert names where to go
    assert signals.read_state(str(repo), topic) is None  # episode NOT marked handled
    # Unmarked means un-given-up-on: the next idle tick tries the nudge again.
    clock["t"] += _supervisor_config.IDLE_NUDGE_AFTER + 1
    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track, act=True)
    assert nudge_count(fake) == 2  # re-attempted, not silently marked handled


def test_pane_that_vanishes_mid_tick_is_session_gone_and_never_acted_on(tmp_path):
    """RB3: the mapped session passes `session_exists` but dies before its pane id is
    resolved. With no pane id there is nothing safe to target — a bare `-t <name>` could
    fall back to a live SIBLING session and `respawn-pane -k` could kill IT — so the row
    degrades to `session-gone` and no pane op runs, even on a valid `ready`."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()  # no live Claude for the topic outside tmux either
    sup = adopt_sup(tmp_path, fake, sessions_dir, {}, {})
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)
    exists = fake.session_exists

    def vanishing_exists(name):
        answer = exists(name)
        fake.sessions.discard(session)  # the pane dies right after we looked
        return answer

    fake.session_exists = vanishing_exists

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)

    assert view.status == "session-gone"
    assert view.tmux is None  # never name a session that is not there
    assert not fake.has("respawn")  # nothing was targeted...
    assert not fake.has("paste")
    assert marker.exists()  # ...and the declaration survives for a later tick


def test_restart_keeps_the_marker_when_the_respawned_pane_never_becomes_claude(tmp_path):
    """B5: the respawn SUCCEEDS but the pane comes up as a bare shell (the launch died
    immediately). The round must NOT be closed — the daemon alerts and keeps the `ready`
    declaration + stamp so the restart retries, rather than reporting a launch it could
    not verify. The Claude twin of the Codex `never becomes codex` guard."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    on_respawn(fake, lambda s: fake.cmds.__setitem__(s, "zsh"))  # comes up a shell
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(mapped_track(repo, topic, session), act=True)

    assert "respawned pane never became Claude" in err.getvalue()
    assert session in err.getvalue()  # the alert names where to go
    assert marker.exists()  # declaration preserved for the retry
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) == 1000.0
    assert supervisor.default_resume(str(repo), topic) not in fake.paste_texts()


def test_freshly_restarted_pane_on_a_gate_pends_the_resume_instead_of_keystroking_it(tmp_path):
    """Blocker #6: the fresh Claude came up on a trust/update/permissions PICKER. Pasting
    the resume line + Enter there would auto-accept the picker's default, so the daemon
    keystrokes NOTHING: it records a round-scoped `resume_pending`, alerts, and leaves the
    `ready` marker in place for the next tick to retry once the human clears the gate."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    gate = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    on_respawn(fake, lambda s: fake.panes.__setitem__(s, gate))  # fresh TUI opens on a gate
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    marker = arm_ready_marker(repo, topic, mtime=1001.0)
    err = _io.StringIO()

    with contextlib.redirect_stderr(err):
        sup.evaluate(mapped_track(repo, topic, session), act=True)

    assert "freshly-restarted pane is on a gate" in err.getvalue()
    assert not fake.has("paste")  # NEVER keystroked the picker
    assert not any(c[0] == "keys" for c in fake.calls)
    assert registry.read_resume_pending(str(repo), topic, sup.stamp_path) is True
    assert marker.exists()  # round left open for the retry
