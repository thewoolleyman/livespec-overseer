"""Claude Code peer-channel resolution from its live session registry."""

from __future__ import annotations

import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from claude_sessions import default_sessions_dir, proc_starttime

if TYPE_CHECKING:
    from _supervisor_channel import MessageChannel
    from _supervisor_core import Supervisor

__all__: list[str] = ["claude_peer_channel_provider"]


@dataclass(frozen=True, kw_only=True)
class ClaudePeerChannel:
    """The channel object addressed by the daemon's already-proven live identity."""

    addressed_identity: str
    name: str = "claude-code-peer"


def claude_peer_channel_provider(
    *,
    sup: Supervisor,
    runtime: str,
    session: str,
    topic: str,
    identity: str | None,
) -> MessageChannel | None:
    """Return a channel only for a matching, live Claude peer socket."""
    del sup, session, topic
    peer = _peer_for(runtime=runtime, identity=identity)
    return (
        cast("MessageChannel", ClaudePeerChannel(addressed_identity=identity or ""))
        if peer is not None
        else None
    )


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
