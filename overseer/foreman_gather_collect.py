"""Compose the deterministic foreman evidence document."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Protocol, TypeAlias, cast

import jsonio
from _supervisor_snapshot import DEFAULT_STATUS_PATH, SCHEMA_VERSION
from foreman_gather_sources import (
    command_skipped,
    default_needs_attention_command,
    read_journal,
    run_json_command,
)

ValidationError: TypeAlias = ValueError

__all__: list[str] = [
    "DOCUMENT_SCHEMA_VERSION",
    "ValidationError",
    "compose_document",
]

DOCUMENT_SCHEMA_VERSION: Final[int] = 1
DEFAULT_JOURNAL_LIMIT: Final[int] = 20


class TimeSource(Protocol):
    def __call__(self) -> str: ...


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validated_snapshot(*, document: dict[str, object], source_name: str) -> list[dict[str, object]]:
    schema = document.get("schema_version")
    rows = jsonio.as_list(value=document.get("rows"))
    generation = document.get("tick_generation")
    if schema != SCHEMA_VERSION or rows is None:
        msg = f"{source_name} snapshot has malformed primitive fields"
        raise ValueError(msg)
    if isinstance(generation, bool) or not isinstance(generation, int):
        msg = f"{source_name} snapshot has malformed tick_generation"
        raise TypeError(msg)
    narrowed: list[dict[str, object]] = []
    for row in rows:
        obj = jsonio.as_object(value=row)
        if obj is None:
            msg = f"{source_name} snapshot row is not an object"
            raise ValueError(msg)
        narrowed.append(obj)
    return narrowed


def snapshot_payload(
    *,
    repo: Path,
    document: dict[str, object],
    mode: str,
    path: Path | None,
) -> tuple[dict[str, object], dict[str, object]]:
    rows = validated_snapshot(document=document, source_name="status")
    repo_text = str(repo)
    used = [row for row in rows if row.get("repo") == repo_text]
    snapshot = {
        "daemon_instance_id": document.get("daemon_instance_id"),
        "tick_generation": document.get("tick_generation"),
        "written_at": document.get("written_at"),
        "rows": used,
    }
    source: dict[str, object] = {
        "status": "ok",
        "mode": mode,
        "rows_total": len(rows),
        "rows_used": len(used),
    }
    if path is not None:
        source["path"] = str(path)
        source["freshness"] = {
            "mtime": path.stat().st_mtime,
            "tick_generation": document.get("tick_generation"),
            "written_at": document.get("written_at"),
        }
    return snapshot, source


def read_snapshot(
    *,
    repo: Path,
    snapshot_path: Path,
    list_json_command: Sequence[str] | None,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    try:
        text = snapshot_path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if text:
        parsed = jsonio.parse_object(text=text)
        if parsed is None:
            msg = "snapshot produced malformed or non-object JSON"
            raise ValueError(msg)
        return snapshot_payload(
            repo=repo, document=parsed, mode="daemon-snapshot", path=snapshot_path
        )
    return read_snapshot_fallback(repo=repo, snapshot_path=snapshot_path, command=list_json_command)


def read_snapshot_fallback(
    *, repo: Path, snapshot_path: Path, command: Sequence[str] | None
) -> tuple[dict[str, object] | None, dict[str, object]]:
    if command is None:
        return None, {
            "status": "skipped",
            "path": str(snapshot_path),
            "reason": "snapshot unavailable and no list --json fallback configured",
        }
    parsed = run_json_command(command=command, source_name="list_json")
    if parsed is None:
        return None, command_skipped(command=command, reason="command not found")
    skip = parsed.get("__skip_reason__")
    if isinstance(skip, str):
        return None, command_skipped(command=command, reason=skip)
    return snapshot_payload(
        repo=repo, document=parsed, mode="list-json-observation-only", path=None
    )


def read_needs_attention(
    *, command: Sequence[str] | None
) -> tuple[dict[str, object] | None, dict[str, object]]:
    if command is None:
        return None, {"status": "skipped", "reason": "command not configured"}
    parsed = run_json_command(command=command, source_name="needs_attention")
    if parsed is None:
        return None, command_skipped(command=command, reason="command not found")
    skip = parsed.get("__skip_reason__")
    if isinstance(skip, str):
        return None, command_skipped(command=command, reason=skip)
    return parsed, {"status": "ok", "command": list(command)}


def option_time(*, options: Mapping[str, object]) -> str:
    maybe = options.get("now")
    if maybe is None:
        return utc_now()
    if not callable(maybe):
        msg = "now option must be callable"
        raise TypeError(msg)
    value = cast("TimeSource", maybe)()
    return value


def option_journal_limit(*, options: Mapping[str, object]) -> int:
    value = options.get("journal_limit")
    if value is None:
        return DEFAULT_JOURNAL_LIMIT
    if isinstance(value, bool) or not isinstance(value, int):
        msg = "journal_limit option must be int"
        raise TypeError(msg)
    return value


def option_journal_path(*, repo: Path, options: Mapping[str, object]) -> Path:
    value = options.get("journal_path")
    if value is None:
        return repo / "tmp/fabro-dispatch-journal.jsonl"
    if isinstance(value, str):
        return Path(value)
    if isinstance(value, Path):
        return value
    msg = "journal_path option must be a path"
    raise TypeError(msg)


def compose_document(
    *,
    repo: str | os.PathLike[str],
    snapshot_path: str | os.PathLike[str] = DEFAULT_STATUS_PATH,
    list_json_command: Sequence[str] | None = None,
    needs_attention_command: Sequence[str] | None = (),
    **options: object,
) -> dict[str, object]:
    repo_path = Path(repo).resolve()
    needs_command = (
        default_needs_attention_command(repo=repo_path)
        if needs_attention_command == ()
        else needs_attention_command
    )
    snapshot, snapshot_source = read_snapshot(
        repo=repo_path,
        snapshot_path=Path(snapshot_path),
        list_json_command=list_json_command,
    )
    attention, attention_source = read_needs_attention(command=needs_command)
    journal_records, journal_source = read_journal(
        path=option_journal_path(repo=repo_path, options=options),
        limit=option_journal_limit(options=options),
    )
    return {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "generated_at": option_time(options=options),
        "repo": str(repo_path),
        "sources": {
            "snapshot": snapshot_source,
            "needs_attention": attention_source,
            "dispatch_journal": journal_source,
        },
        "snapshot": snapshot,
        "needs_attention": attention,
        "dispatch_journal": journal_records,
    }
