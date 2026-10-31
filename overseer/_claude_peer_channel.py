"""Claude Code peer-channel resolution from its live session registry."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import TYPE_CHECKING

from claude_sessions import default_sessions_dir, proc_starttime

if TYPE_CHECKING:
    from _supervisor_channel import MessageChannel
    from _supervisor_core import Supervisor

__all__: list[str] = ["claude_peer_channel_provider"]


def claude_peer_channel_provider(
    *,
    sup: Supervisor,
    runtime: str,
    session: str,
    topic: str,
    identity: str | None,
) -> MessageChannel | None:
    """Decline Claude's peer socket because it cannot acknowledge acceptance.

    Claude Code 2.1.170's ``sendToUdsSocket`` sends the framed message and
    resolves on socket close without parsing a response.  A matching live socket
    can establish the address, but cannot prove that the receiving session
    accepted the specific message.  The channel contract therefore requires the
    existing guarded-paste path.
    """
    del sup, session, topic
    _ = _peer_for(runtime=runtime, identity=identity)
    return None


def _peer_for(*, runtime: str, identity: str | None) -> Path | None:
    try:
        prefix, pid_text, proc_start, name = (identity or "").split(":", 3)
        pid = int(pid_text)
        record = json.loads((default_sessions_dir() / f"{pid}.json").read_text(encoding="utf-8"))
        path = Path(record["messagingSocketPath"])
        expected = (prefix, record["pid"], record["procStart"], record["name"])
        live = proc_starttime(pid=pid)
        is_socket = stat.S_ISSOCK(path.lstat().st_mode)
    except (KeyError, OSError, TypeError, ValueError):
        return None
    return (
        path
        if (
            runtime == "claude"
            and expected == ("claude", pid, proc_start, name)
            and live == proc_start
            and record.get("peerProtocol") == 1
            and path.is_absolute()
            and path.name == f"{pid}.sock"
            and is_socket
        )
        else None
    )
