"""Beside-tests for supervisor.py — tHE CARDINAL RULE + the ONE tri-state indicator file (maintaine.

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
import supervisor
from test_supervisor_builders import (
    declare,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import (
    FakeTmux,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


# --------------------------------------------------------------------------- #
# THE CARDINAL RULE + the ONE tri-state indicator file (maintainer 2026-07-14).
#
# The daemon NEVER restarts a session that has not declared itself `ready`. It never
# infers readiness from a timer or from idleness — "idle + settled" is NOT "safe to
# kill". A session that declares nothing is REPORTED, never killed.
# --------------------------------------------------------------------------- #


def test_idle_at_danger_with_no_declaration_is_never_restarted(tmp_path):
    """THE regression guard for the severe bug. A session idle at 13%, warned, wide past
    any plausible timeout, having declared NOTHING, must be SURFACED and left alone —
    never respawned. A timer cannot know a session is safe to kill."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=13))  # idle, deep in danger, no state
    sup = make_supervisor(tmp_path, fake)
    track = mapped_track(repo, topic, session)

    for _ in range(20):  # tick and tick and tick — it must NEVER escalate to a kill
        view = sup.evaluate(track, act=True)
    assert view.status == "danger"
    assert not fake.has("respawn")  # the session was NOT killed
    assert not signals.state_path(str(repo), topic).exists()  # daemon wrote nothing


def test_restart_fires_only_on_a_declared_ready(tmp_path):
    """`ready` is the SOLE authorization. Declared → restarted immediately; the state
    file is then cleared so it cannot re-trigger."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    state = declare(repo, topic, "ready", mtime=1001.0)

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "restarting"
    assert fake.has("respawn")
    assert supervisor.default_resume(str(repo), topic) in fake.paste_texts()
    assert not state.exists()  # round closed
    assert registry.read_injection_stamp(str(repo), topic, sup.stamp_path) is None


def test_winding_down_ack_suppresses_the_rewarn(tmp_path):
    """A fresh `winding-down` ACK buys patience: the session heard us and is wrapping up,
    so the daemon stops re-warning — it must never keystroke into a session that is
    actively winding down. It is NOT restarted either (only `ready` does that)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=13))  # would otherwise be `danger`
    sup = make_supervisor(tmp_path, fake)  # now() == 1000.0
    declare(repo, topic, "winding-down", mtime=1000.0)  # fresh ACK

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "winding-down"
    assert not fake.has("paste")  # no re-warn pasted into a session that is wrapping up
    assert not fake.has("respawn")  # an ACK is not a restart authorization


def test_stale_winding_down_ack_resumes_escalation_but_still_never_acts(tmp_path):
    """An ACK must not become an infinite stall. Past `ACK_STALE_AFTER` the daemon
    resumes escalating and reports the track — but it STILL never kills it. The
    escalation is louder words, never a restart."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=13))
    err = _io.StringIO()
    sup = make_supervisor(tmp_path, fake)  # now() == 1000.0
    declare(repo, topic, "winding-down", mtime=1000.0 - _supervisor_config.ACK_STALE_AFTER - 1)

    with contextlib.redirect_stderr(err):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "danger"  # the stale ACK no longer protects it
    assert fake.has("paste")  # escalation resumed
    assert not fake.has("respawn")  # but STILL never killed
    # The report must NOT conflate "hung mid-wrap-up" with "ignored us" — they need
    # different fixes, and this session DID acknowledge.
    out = err.getvalue()
    assert "ACKNOWLEDGED the wrap-up" in out
    assert "declared NOTHING" not in out


def test_blocked_declaration_is_surfaced_and_never_restarted(tmp_path):
    """`blocked` carries its one-line reason into the row, and the track is never
    keystroked or restarted — a human gate is the one thing the daemon must not touch."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=13))
    sup = make_supervisor(tmp_path, fake)
    declare(repo, topic, "blocked: waiting on the schema call")

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    assert view.note == "waiting on the schema call"
    assert not fake.has("paste")
    assert not fake.has("respawn")


def test_one_file_cannot_be_both_ready_and_blocked(tmp_path):
    """The reason for ONE file with a VALUE: with two presence-markers, both could exist
    and the precedence was incidental. A single file makes the ambiguity unrepresentable
    — writing `blocked` REPLACES `ready`, so the track is blocked, full stop."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    declare(repo, topic, "ready", mtime=1001.0)
    declare(repo, topic, "blocked: changed my mind", mtime=1002.0)  # same file, overwritten

    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "blocked:human"
    assert not fake.has("respawn")  # the superseded `ready` cannot restart it


def test_malformed_state_value_is_surfaced_and_never_restarts(tmp_path):
    """A typo'd value must be REPORTED, not silently ignored — and must never be read as
    readiness (fail-closed)."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=30))
    err = _io.StringIO()
    sup = make_supervisor(tmp_path, fake)
    registry.write_injection_stamp(str(repo), topic, 1000.0, sup.stamp_path)
    declare(repo, topic, "redy", mtime=1001.0)  # typo

    with contextlib.redirect_stderr(err):
        view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert not fake.has("respawn")  # a typo is NOT a restart authorization
    assert "MALFORMED state file" in err.getvalue()
    assert view.note is not None and "redy" in view.note


def test_every_track_alert_names_the_tmux_session_and_pane(tmp_path):
    """Operator-facing alerts must say WHERE to act: `repo::topic` alone told the
    maintainer WHAT was stuck but not WHERE to go. Every track alert carries the tmux
    session, the pane, and a copy-pasteable jump command."""
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.serve(session, repo, capture=idle_capture(ctx=13))  # danger, nothing declared
    err = _io.StringIO()
    sup = make_supervisor(tmp_path, fake)

    with contextlib.redirect_stderr(err):
        sup.evaluate(mapped_track(repo, topic, session), act=True)
    out = err.getvalue()
    assert topic in out
    assert f"tmux session '{session}'" in out
    assert f"pane {session}" in out  # FakeTmux models the pane id as the session name
    assert f"tmux switch-client -t {session}" in out  # the jump command


# --------------------------------------------------------------------------- #
# session-gone (mapped row, session missing).
# --------------------------------------------------------------------------- #


def test_mapped_track_with_missing_session(tmp_path):
    repo, topic = make_plan(tmp_path)
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()  # session NOT added
    sup = make_supervisor(tmp_path, fake)
    view = sup.evaluate(mapped_track(repo, topic, session), act=True)
    assert view.status == "session-gone"
    assert not fake.has("capture")


# --------------------------------------------------------------------------- #
# auto-link: repo-qualified + cwd-verified; refuses a cross-repo session.
# --------------------------------------------------------------------------- #


def test_auto_link_refuses_different_repo(tmp_path):
    repo, topic = make_plan(tmp_path)
    other_repo = tmp_path / "other-repo"
    other_repo.mkdir()
    session = registry.tmux_id(str(repo), topic)
    fake = FakeTmux()
    fake.sessions.add(session)
    fake.paths[session] = str(other_repo)  # session cwd is a DIFFERENT repo
    sup = make_supervisor(tmp_path, fake, watch_repos=[str(repo)])

    unassigned = registry.Track.make_unassigned(
        repo=str(repo), topic=topic, handoff=supervisor.default_handoff(str(repo), topic)
    )
    assert sup.auto_link(unassigned) is None
    assert registry.read_mapping(sup.store_path) == []  # nothing linked
