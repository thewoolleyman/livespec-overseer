"""Per-tick status snapshot export for the overseer daemon.

The live table remains the daemon's primary operator surface. This module writes a
read-only JSON projection of that same row set so deterministic consumers can observe
the daemon without scraping tmux output. It deliberately serializes only bounded row
notes: a session-authored ``blocked:`` reason is evidence, not an instruction channel,
and the snapshot must not become another unelided pane-text surface.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio
import registry
from _supervisor_view import RowView, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "DEFAULT_STATUS_PATH",
    "SCHEMA_VERSION",
    "SNAPSHOT_NOTE_LIMIT",
    "SnapshotFreshness",
    "StatusSnapshotRead",
    "default_status_writer",
    "read_status_snapshot",
    "snapshot_unchanged",
    "write_status_snapshot",
]

SCHEMA_VERSION = 1
SNAPSHOT_NOTE_LIMIT = 48
DEFAULT_STATUS_PATH = Path.home() / ".livespec-overseer-status.json"


@dataclass(frozen=True, kw_only=True)
class SnapshotFreshness:
    generation: int
    mtime: float


@dataclass(frozen=True, kw_only=True)
class StatusSnapshotRead:
    document: dict[str, object]
    freshness: SnapshotFreshness

    @property
    def generation(self) -> int:
        return self.freshness.generation

    @property
    def mtime(self) -> float:
        return self.freshness.mtime


def snapshot_unchanged(*, previous: SnapshotFreshness, current: SnapshotFreshness) -> bool:
    return previous.generation == current.generation and previous.mtime == current.mtime


def default_status_writer(*, path: Path, body: str) -> None:
    with registry.file_lock(target=path):
        registry.atomic_write(path=path, body=body, raise_errors=True)


def _written_at(*, timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot_note(*, row: RowView) -> str | None:
    if row.note is None:
        return None
    text = elide(text=row.note, limit=SNAPSHOT_NOTE_LIMIT)
    if text.endswith("…"):
        return text[: SNAPSHOT_NOTE_LIMIT - 3].rstrip() + "..."
    return text


def row_payload(*, sup: Supervisor, row: RowView) -> dict[str, object]:
    return {
        "topic": row.topic,
        "repo": row.repo,
        "tmux": row.tmux,
        "runtime": row.runtime,
        "status": row.status,
        "note": _snapshot_note(row=row),
        "ctx": row.ctx,
        "progress_now": row.progress_now,
        "human_wait": row.human_wait,
        "round_open": row.round_open,
        "acked": row.acked,
        "session_identity": session_identity(sup=sup, row=row),
    }


def session_identity(*, sup: Supervisor, row: RowView) -> str:
    if row.tmux is None:
        return f"none:{row.repo}:{row.topic}"
    if row.runtime == "codex":
        live = sup.live_codex.get((row.tmux, row.topic))
        if live is not None:
            return f"codex:{live.session_id}"
    if row.runtime == "claude":
        identity = sup.claude_identity_by_session.get((row.tmux, row.topic))
        return identity if identity is not None else f"claude:{row.tmux}:{row.topic}"
    return f"tmux:{row.tmux}:{row.topic}"


def document_payload(*, sup: Supervisor, rows: list[RowView]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "daemon_instance_id": sup.daemon_instance_id,
        "tick_generation": sup.tick_generation,
        "written_at": _written_at(timestamp=sup.now()),
        "rows": [row_payload(sup=sup, row=row) for row in rows],
    }


def write_status_snapshot(*, sup: Supervisor, rows: list[RowView]) -> None:
    if sup.status_path is not None:
        path = Path(sup.status_path)
    elif sup.status_snapshot_path is not None:
        path = Path(sup.status_snapshot_path)
    else:
        path = DEFAULT_STATUS_PATH
    body = json.dumps(document_payload(sup=sup, rows=rows), indent=2, sort_keys=True) + "\n"
    sup.status_writer(path=path, body=body)


def read_status_snapshot(*, path: str | os.PathLike[str]) -> StatusSnapshotRead | None:
    target = Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
        stat = target.stat()
    except OSError:
        return None
    document = jsonio.parse_object(text=raw)
    if document is None:
        return None
    schema = document.get("schema_version")
    generation = document.get("tick_generation")
    if not isinstance(schema, int) or schema != SCHEMA_VERSION:
        return None
    if isinstance(generation, bool) or not isinstance(generation, int):
        return None
    return StatusSnapshotRead(
        document=document,
        freshness=SnapshotFreshness(generation=generation, mtime=stat.st_mtime),
    )
