"""_supervisor_status_snapshot — per-tick machine-readable daemon row export.

The live table remains the operator surface. This module writes the additive
observation-only JSON snapshot consumed by deterministic tooling such as the
foreman. It deliberately serializes from the already-built ``RowView`` list and
is never read back by the daemon.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from _registry_core import atomic_write, file_lock
from _supervisor_view import RowView, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "DEFAULT_STATUS_SNAPSHOT_PATH",
    "MAX_NOTE_IN_SNAPSHOT",
    "STATUS_SNAPSHOT_SCHEMA_VERSION",
    "write_status_snapshot",
]

STATUS_SNAPSHOT_SCHEMA_VERSION = 1
MAX_NOTE_IN_SNAPSHOT = 80
DEFAULT_STATUS_SNAPSHOT_PATH = Path.home() / ".livespec-overseer-status.json"


def _written_at(*, timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_path(*, sup: Supervisor) -> Path:
    if sup.status_snapshot_path is None:
        return DEFAULT_STATUS_SNAPSHOT_PATH
    return Path(sup.status_snapshot_path)


def _identity_token(*, sup: Supervisor, row: RowView) -> str | None:
    if row.tmux is None:
        return None
    if row.runtime == "codex":
        live = sup.live_codex.get((row.tmux, row.topic))
        if live is not None:
            return f"codex:{live.session_id}"
    if row.runtime == "claude":
        identity = sup.claude_identity_by_session.get((row.tmux, row.topic))
        if identity is not None:
            return identity
        return f"claude:{row.tmux}:{row.topic}"
    return f"{row.runtime or 'unknown'}:{row.tmux}:{row.topic}"


def _note(*, row: RowView) -> str | None:
    if row.note is None:
        return None
    text = elide(text=row.note, limit=MAX_NOTE_IN_SNAPSHOT)
    if text.endswith("…"):
        return text[: MAX_NOTE_IN_SNAPSHOT - 3].rstrip() + "..."
    return text


def _row(*, sup: Supervisor, row: RowView) -> dict[str, object]:
    return {
        "topic": row.topic,
        "repo": row.repo,
        "tmux": row.tmux,
        "runtime": row.runtime,
        "status": row.status,
        "note": _note(row=row),
        "ctx": row.ctx,
        "progress_now": row.progress_now,
        "human_wait": row.human_wait,
        "round_open": row.round_open,
        "acked": row.acked,
        "session_identity": _identity_token(sup=sup, row=row),
    }


def write_status_snapshot(*, sup: Supervisor, rows: list[RowView]) -> None:
    path = _snapshot_path(sup=sup)
    body = json.dumps(
        {
            "schema_version": STATUS_SNAPSHOT_SCHEMA_VERSION,
            "daemon_instance_id": sup.daemon_instance_id,
            "tick_generation": sup.tick_generation,
            "written_at": _written_at(timestamp=sup.now()),
            "rows": [_row(sup=sup, row=row) for row in rows],
        },
        indent=2,
        sort_keys=True,
    )
    with file_lock(target=path):
        atomic_write(path=path, body=body + "\n", raise_errors=True)
