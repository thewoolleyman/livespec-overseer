"""Evaluation-time reads of the already-joined Claude registry file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import claude_sessions

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "FreshClaudeRegistry",
    "current_status",
    "drop_unjoined_status",
    "read_joined_registry",
    "status",
]

_CLAUDE_IDENTITY_PARTS = 4


@dataclass(frozen=True, kw_only=True)
class FreshClaudeRegistry:
    """One exact-file re-read, tied to discovery's authoritative pane join."""

    session: claude_sessions.ClaudeSession | None
    read_at: float


def _joined_pid(*, identity: str | None) -> tuple[int, str] | None:
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
    joined = _joined_pid(identity=sup.claude_identity_by_session.get((session, topic)))
    return None if joined is None else _read_joined(sup=sup, joined=joined)


def _read_joined(*, sup: Supervisor, joined: tuple[int, str]) -> FreshClaudeRegistry:
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


def drop_unjoined_status(*, sup: Supervisor) -> None:
    """Drop discovery-snapshot statuses whose session has no joined identity.

    The status and identity snapshots are separate registry passes; a record that changed
    between them leaves a status no evaluation-time re-read can verify.
    """
    joined = {s for (s, _), v in sup.claude_identity_by_session.items() if _joined_pid(identity=v)}
    sup.claude_status_by_session = {
        s: v for s, v in sup.claude_status_by_session.items() if s in joined
    }


def status(*, sup: Supervisor, session: str, topic: str) -> tuple[str | None, float | None]:
    """Return the current joined self-report and its read time for one evaluation.

    Never returns the cycle-start snapshot for a session that has a join: an unreadable
    or invalid joined record yields no self-report at all, so a stale value cannot drive
    a busy decision or a row note.
    """
    identities = sup.claude_identity_by_session
    exact = identities.get((session, topic))
    # Same last-wins pick as the discovery snapshot, but re-read now.
    candidates = (
        [exact] if exact else [v for (s, _), v in reversed(identities.items()) if s == session]
    )
    joined = next((j for v in candidates if (j := _joined_pid(identity=v)) is not None), None)
    if joined is None:
        # Discovery drops unjoined snapshots, so only injected state remains here.
        return sup.claude_status_by_session.get(session), None
    fresh = _read_joined(sup=sup, joined=joined)
    if fresh.session is None:
        return None, fresh.read_at
    live = fresh.session
    if exact is not None:
        identities[(session, topic)] = f"claude:{live.pid}:{live.proc_start}:{live.name}"
    return live.status, fresh.read_at


current_status = status
