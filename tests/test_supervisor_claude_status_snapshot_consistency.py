"""A discovery status with no joined identity never survives into evaluation."""

from __future__ import annotations

import contextlib
import importlib
import io as _io
from types import SimpleNamespace

import claude_sessions
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


def test_drop_unjoined_status_keeps_only_sessions_with_a_parseable_join():
    """Statuses lacking a joined ``claude:<pid>:<start>:<name>`` identity are dropped."""
    freshness = importlib.import_module("_supervisor_claude_registry_freshness")
    sup = SimpleNamespace(
        claude_status_by_session={"joined": "idle", "missing": "busy", "codex": "busy"},
        claude_identity_by_session={
            ("joined", "topic"): "claude:100:pt:topic",
            ("codex", "topic"): "codex:100:pt:topic",
        },
    )

    freshness.drop_unjoined_status(sup=sup)

    assert sup.claude_status_by_session == {"joined": "idle"}


def test_status_changed_between_discovery_passes_does_not_defer_a_ready_restart(
    *, tmp_path, monkeypatch
):
    """A status the identity pass could not join cannot render an idle pane as busy."""
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=30))
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fake.pane_pids[50] = session
    write_session(sessions_dir=sessions_dir, pid=100, name=topic, cwd=repo, status="busy")
    sup = adopt_sup(
        tmp_path=tmp_path,
        fake=fake,
        sessions_dir=sessions_dir,
        ppid={100: 50},
        starttimes={100: "pt"},
    )
    monkeypatch.setattr(claude_sessions, "identities_by_tmux_session", lambda **_: {})

    sup._refresh_claude_status()

    assert sup.claude_status_by_session == {}
    registry.write_injection_stamp(
        repo=str(repo),
        topic=topic,
        ts=1000.0,
        session_identity="claude:100:pt:topic",
        stamp_path=sup.stamp_path,
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)
    assert "Claude busy" not in (view.note or "")
