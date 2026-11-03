"""Evaluation-time reads of the already-joined Claude registry file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import claude_sessions

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["FreshClaudeRegistry", "current_status", "read_joined_registry", "status"]

_CLAUDE_IDENTITY_PARTS = 4


@dataclass(frozen=True, kw_only=True)
class FreshClaudeRegistry:
    """One exact-file re-read, tied to discovery's authoritative pane join."""

    session: claude_sessions.ClaudeSession | None
    read_at: float


def _joined_pid(*, sup: Supervisor, session: str, topic: str) -> tuple[int, str] | None:
    identity = sup.claude_identity_by_session.get((session, topic))
    if identity is None:
        return None
    parts = identity.split(":", 3)
    if len(parts) != _CLAUDE_IDENTITY_PARTS or parts[0] != "claude":
        return None
    try:
        return int(parts[1]), parts[2]
    except ValueError:
        return None


def read_joined_registry(
    *, sup: Supervisor, session: str, topic: str
) -> FreshClaudeRegistry | None:
    """Re-read only the registry file discovery already joined to ``session``.

    Discovery's parent-PID walk remains the authoritative pane join. Evaluation does
    not repeat it or list panes; it merely verifies that exact joined PID's current
    registry record and process identity, failing closed when the record disappeared
    or became malformed.
    """
    joined = _joined_pid(sup=sup, session=session, topic=topic)
    if joined is None:
        return None
    pid, expected_start = joined
    directory = (
        Path(sup.sessions_dir)
        if sup.sessions_dir is not None
        else claude_sessions.default_sessions_dir()
    )
    try:
        parsed = json.loads((directory / f"{pid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FreshClaudeRegistry(session=None, read_at=sup.now())
    if not isinstance(parsed, dict):
        return FreshClaudeRegistry(session=None, read_at=sup.now())
    data = cast(dict[object, object], parsed)
    name, cwd, proc_start, status = (
        data.get("name"),
        data.get("cwd"),
        data.get("procStart"),
        data.get("status"),
    )
    if not (
        data.get("pid") == pid
        and isinstance(name, str)
        and name
        and isinstance(cwd, str)
        and cwd
        and str(proc_start) == expected_start
        and sup.starttime_of(pid=pid) == expected_start
    ):
        return FreshClaudeRegistry(session=None, read_at=sup.now())
    return FreshClaudeRegistry(
        session=claude_sessions.ClaudeSession(
            pid=pid,
            name=name,
            cwd=cwd,
            status=status if isinstance(status, str) else "",
            proc_start=expected_start,
            name_source=(
                name_source if isinstance(name_source := data.get("nameSource"), str) else ""
            ),
        ),
        read_at=sup.now(),
    )


def status(*, sup: Supervisor, session: str, topic: str) -> tuple[str | None, float | None]:
    """Return the current joined self-report and its read time for one evaluation."""
    fresh = read_joined_registry(sup=sup, session=session, topic=topic)
    if fresh is None or fresh.session is None:
        return sup.claude_status_by_session.get(session), None
    live = fresh.session
    sup.claude_identity_by_session[(session, topic)] = (
        f"claude:{live.pid}:{live.proc_start}:{live.name}"
    )
    return live.status, fresh.read_at


current_status = status
