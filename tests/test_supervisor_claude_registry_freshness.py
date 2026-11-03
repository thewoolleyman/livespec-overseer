"""Regression coverage for per-track Claude registry freshness."""

from __future__ import annotations

import contextlib
import io as _io

import pytest
import registry
from test_supervisor_builders import (
    adopt_sup,
    arm_ready_marker,
    idle_capture,
    make_plan,
    mapped_track,
    write_session,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []


@pytest.fixture(autouse=True)
def _isolate_cwd(*, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_ready_track_uses_idle_registry_status_written_after_discovery(*, tmp_path):
    """A ready track restarts when its already-joined registry file turns idle."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    ppid = {100: 50}
    starttimes = {100: "pt"}
    fake.pane_pids[50] = session
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid=ppid,
        starttimes=starttimes,
    )
    sup._refresh_claude_status()
    assert sup.claude_status_by_session[session] == "busy"
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity="claude:100:pt:topic",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)

    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="idle")

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    assert view.status == "restarting"
    assert view.note is None
    assert fake.has(method="respawn")
