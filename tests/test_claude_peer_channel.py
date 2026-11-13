"""Claude Code's session-bound peer channel provider."""

from __future__ import annotations

import importlib
import json
import socket
from pathlib import Path


def _listen(*, path: Path) -> socket.socket:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen()
    return listener


def _write_session(*, sessions_dir: Path, socket_path: Path) -> None:
    sessions_dir.mkdir()
    (sessions_dir / "123.json").write_text(
        json.dumps(
            {
                "pid": 123,
                "name": "worker",
                "cwd": "/repo",
                "procStart": "456",
                "peerProtocol": 1,
                "sessionId": "session-uuid",
                "messagingSocketPath": str(socket_path),
            }
        ),
        encoding="utf-8",
    )


def test_a_claude_peer_socket_without_an_acceptance_reply_is_not_supported(
    *, tmp_path, monkeypatch
):
    """A Claude UDS peer with no per-message acceptance acknowledgement falls back.

    Measured against Claude Code 2.1.170: its ``sendToUdsSocket`` writes a framed
    ``user`` object, then resolves when the connection closes.  It does not parse a
    reply from the receiving session, so it cannot prove acceptance as required by
    the daemon channel contract.
    """
    peer_module = importlib.import_module("_claude_peer_channel")
    channel_module = importlib.import_module("_supervisor_channel")
    sessions_dir = tmp_path / "sessions"
    socket_dir = tmp_path / "cc-socks"
    socket_dir.mkdir()
    peer_socket = socket_dir / "123.sock"
    listener = _listen(path=peer_socket)
    _write_session(sessions_dir=sessions_dir, socket_path=peer_socket)
    monkeypatch.setattr(peer_module, "default_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr(peer_module, "proc_starttime", lambda *, pid: "456" if pid == 123 else None)
    try:
        channel = channel_module.resolve_channel(
            sup=object(),
            runtime="claude",
            session="tmux-worker",
            topic="worker",
            identity="claude:123:456:worker",
        )
    finally:
        listener.close()

    assert channel is None
