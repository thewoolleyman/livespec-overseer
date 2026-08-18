"""Regression tests for Claude restart post-respawn liveness verification."""

import contextlib
import io as _io

import registry
import signals
from test_supervisor_builders import (
    arm_ready_marker,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


def test_a_claude_restart_with_no_post_respawn_live_process_is_not_success(*, tmp_path):
    """A Claude-looking foreground command is not enough after respawn."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.claude_identity_by_session[(session, topic)] = "claude:old:identity"
    sup.refresh_claude_status = lambda: sup.claude_identity_by_session.clear()
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity="claude:old:identity",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    log = _io.StringIO()
    with contextlib.redirect_stderr(log):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_READY
    assert registry.read_resume_pending(repo=str(repo), topic=topic, stamp_path=sup.stamp_path)
    assert "no live Claude process" in log.getvalue()
    assert f"restarted {repo}::{topic}" not in log.getvalue()


def test_a_claude_restart_polls_for_post_respawn_live_process(*, tmp_path):
    """A healthy respawn can register its Claude session file after the pane is Claude."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = topic
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity=f"claude:{session}:{session}",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    refreshes = {"count": 0}

    def delayed_refresh() -> None:
        refreshes["count"] += 1
        sup.claude_identity_by_session.clear()
        if refreshes["count"] >= 2:
            sup.claude_identity_by_session[(session, topic)] = f"claude:{session}:{topic}"

    sup.refresh_claude_status = delayed_refresh

    with contextlib.redirect_stderr(_io.StringIO()):
        sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    state = signals.read_state(repo=str(repo), topic=topic)
    assert state is not None
    assert state.token == signals.STATE_RESTARTED
    assert refreshes["count"] == 2
