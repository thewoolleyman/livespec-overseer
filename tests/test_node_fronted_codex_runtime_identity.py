"""Regression tests for Codex panes whose tmux foreground command is `node`."""

from __future__ import annotations

import contextlib
import io as _io
from pathlib import Path

import codex_sessions
import registry
from test_supervisor_builders import (
    arm_ready_marker,
    codex_idle_capture,
    idle_capture,
    make_plan,
    make_supervisor,
    mapped_track,
)
from test_supervisor_fakes import FakeTmux

__all__: list[str] = []

_CODEX_SESSION_ID = "019f6a1e-266d-7fc2-8eb2-15ec9d324fb8"


def _node_codex_subject(*, tmp_path: Path):
    repo, topic = make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=codex_idle_capture(ctx=40), cmd="node")
    fake.pane_pid_map[session] = 142554
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.cmdline_of = lambda *, pid: (
        b"node\x00/home/ubuntu/.bun/bin/codex\x00--dangerously-bypass-approvals\x00"
        if pid == 142554
        else None
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=142608, name=topic, cwd=str(repo), session_id=_CODEX_SESSION_ID
        )
    }
    return repo, topic, session, fake, sup


def _node_claude_control(*, tmp_path: Path):
    repo, topic = make_plan(tmp_path=tmp_path, repo_name="claude-repo", topic="claude-topic")
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = FakeTmux()
    fake.serve(session=session, repo=repo, capture=idle_capture(ctx=80), cmd="node")
    fake.pane_pid_map[session] = 200001
    sup = make_supervisor(tmp_path=tmp_path, fake=fake)
    sup.cmdline_of = lambda *, pid: (
        b"node\x00/home/ubuntu/.bun/bin/claude\x00--dangerously-skip-permissions\x00"
        if pid == 200001
        else None
    )
    sup.live_codex = {
        (session, topic): codex_sessions.CodexSession(
            pid=200010,
            name=topic,
            cwd=str(repo),
            session_id="019f548d-6071-7893-9c2e-472cce81da02",
        )
    }
    return repo, topic, session, sup


def test_node_fronted_codex_track_uses_exact_launcher_identity_for_runtime_and_restart(*, tmp_path):
    """Exact pane argv decides the ambiguous `node` case; basename membership does not."""
    repo, topic, session, fake, sup = _node_codex_subject(tmp_path=tmp_path)

    assert sup._is_codex_track(session=session, repo=str(repo), topic=topic, target=session)
    registry.write_injection_stamp(
        repo=str(repo), topic=topic, ts=1000.0, stamp_path=sup.stamp_path
    )
    arm_ready_marker(repo=repo, topic=topic, mtime=1001.0)
    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=True)

    respawn_commands = [c[3] for c in fake.calls if c[0] == "respawn"]
    assert view.runtime == "codex"
    assert view.status == "restarting"
    assert respawn_commands
    assert "codex resume " in respawn_commands[0]
    assert _CODEX_SESSION_ID in respawn_commands[0]
    assert "claude" not in respawn_commands[0]


def test_real_claude_node_pane_remains_claude_with_ambiguous_codex_evidence(*, tmp_path):
    """A same-session Codex rollout cannot reclassify a Claude pane whose own argv is Claude."""
    repo, topic, session, sup = _node_claude_control(tmp_path=tmp_path)

    with contextlib.redirect_stderr(_io.StringIO()):
        view = sup.evaluate(track=mapped_track(repo=repo, topic=topic, session=session), act=False)

    assert view.runtime == "claude"
    assert not sup._is_codex_track(session=session, repo=str(repo), topic=topic, target=session)
