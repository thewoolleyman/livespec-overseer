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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio
import registry
from _supervisor_statusline_model import rendered_statusline_model
from _supervisor_view import RowView, elide
from version import APP_VERSION

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
    if row.status == "mapping-unusable":
        return row.note
    text = elide(text=row.note, limit=SNAPSHOT_NOTE_LIMIT)
    if text.endswith("…"):
        return text[: SNAPSHOT_NOTE_LIMIT - 3].rstrip() + "..."
    return text


def _track_for_row(*, sup: Supervisor, row: RowView) -> registry.Track | None:
    if not hasattr(sup, "store_path"):
        return None
    store_path = getattr(sup, "store_path", None)
    repo = registry.norm(repo=row.repo)
    for track in registry.read_valid_mapping(store_path=store_path):
        if registry.norm(repo=track.repo) == repo and track.topic == row.topic:
            return track
    return None


def _current_default_model() -> str | None:
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        parsed = jsonio.parse_object(text=settings_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    payload = parsed.unwrap()
    if payload is None:
        return None
    model = payload.get("model")
    return model if isinstance(model, str) and model else None


def _capture_for_row(*, sup: Supervisor, row: RowView) -> str | None:
    if row.tmux is None:
        return None
    tmux = getattr(sup, "tmux", None)
    if tmux is None:
        return None
    return tmux.capture_pane(session=row.tmux)


def _restart_model_payload(
    *,
    current_default: str | None,
    model_profile: Mapping[str, str | None] | None,
    rendered: str | None,
    row: RowView,
) -> dict[str, object]:
    recorded = None if model_profile is None else model_profile.get("statusline_model")
    base: dict[str, object] = {
        "current_default": current_default,
        "rendered_statusline_model": rendered,
        "recorded_statusline_model": recorded,
    }
    if model_profile is not None:
        return {"verdict": "profile-preserved", "reason": "recorded-profile", **base}
    if row.tmux is None:
        return {"verdict": "unknown", "reason": "pane-absent", **base}
    if rendered is None:
        return {"verdict": "unknown", "reason": "statusline-unreadable", **base}
    if current_default is None:
        return {"verdict": "unknown", "reason": "default-unreadable", **base}
    if rendered == current_default:
        return {"verdict": "no-op", "reason": "matches-current-default", **base}
    return {"verdict": "would-change", "reason": "differs-from-current-default", **base}


def restart_model_payload(*, sup: Supervisor, row: RowView) -> dict[str, object]:
    track = _track_for_row(sup=sup, row=row)
    model_profile = None if track is None else track.model_profile
    capture = _capture_for_row(sup=sup, row=row)
    rendered = None if capture is None else rendered_statusline_model(capture=capture)
    return _restart_model_payload(
        current_default=_current_default_model(),
        model_profile=model_profile,
        rendered=rendered,
        row=row,
    )


def row_payload(*, sup: Supervisor, row: RowView) -> dict[str, object]:
    track = _track_for_row(sup=sup, row=row)
    model_profile = None if track is None else track.model_profile
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
        "picker_open": row.picker_open,
        "stall_seconds": row.stall_seconds,
        "supervisor_state_stale": row.supervisor_state_stale,
        "session_identity": session_identity(sup=sup, row=row),
        "model_profile": model_profile,
        "restart_model": restart_model_payload(sup=sup, row=row),
    }


def session_identity(*, sup: Supervisor, row: RowView) -> str:
    if row.tmux is None:
        return f"none:{row.repo}:{row.topic}"
    if row.runtime == "codex":
        live = getattr(sup, "live_codex", {}).get((row.tmux, row.topic))
        if live is not None:
            return f"codex:{live.session_id}"
    if row.runtime == "claude":
        identity = getattr(sup, "claude_identity_by_session", {}).get((row.tmux, row.topic))
        return identity if identity is not None else f"claude:{row.tmux}:{row.topic}"
    return f"tmux:{row.tmux}:{row.topic}"


def daemon_package_payload() -> dict[str, object]:
    return {
        "package_dir": str(Path(__file__).resolve().parent),
        "version": APP_VERSION,
    }


def document_payload(*, sup: Supervisor, rows: list[RowView]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "daemon_package": daemon_package_payload(),
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
    parsed = jsonio.parse_object(text=raw)
    if jsonio.is_parse_failure(result=parsed):
        return None
    document = parsed.unwrap()
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
