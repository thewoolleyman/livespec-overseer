"""Compose the deterministic foreman evidence document."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Protocol, TypeAlias, cast

import jsonio
import signals
from _supervisor_snapshot import DEFAULT_STATUS_PATH
from foreman_gather_release_lane import attention_with_release_lane, release_lane_payload
from foreman_gather_snapshot import (
    migrated_supervisor_handoff_state,
    read_snapshot,
    read_snapshot_fallback,
    row_with_supervisor_handoff,
    snapshot_payload,
    validated_snapshot,
)
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
    "migrated_supervisor_handoff_state",
    "read_snapshot",
    "read_snapshot_fallback",
    "row_with_supervisor_handoff",
    "snapshot_payload",
    "supervisor_handoff_state",
    "validated_snapshot",
]

DOCUMENT_SCHEMA_VERSION: Final[int] = 1
DEFAULT_JOURNAL_LIMIT: Final[int] = 20


class TimeSource(Protocol):
    def __call__(self) -> str: ...


def supervisor_handoff_state(*, repo: Path, topic: object) -> str:
    if not isinstance(topic, str) or topic == "":
        return "unknown"
    if signals.topic_reserved_for_supervisor(topic=topic):
        return "supervisor-topic"
    plan_dir = repo / "plan" / topic
    if not plan_dir.is_dir():
        return "not-plan"
    legacy_path = plan_dir / "supervisor-handoff.md"
    if legacy_path.is_file():
        return "present"
    if migrated_supervisor_handoff_state(repo=repo, topic=topic):
        return "present"
    return "missing"


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    generated_at = option_time(options=options)
    snapshot, snapshot_source = read_snapshot(
        repo=repo_path,
        snapshot_path=Path(snapshot_path),
        list_json_command=list_json_command,
        pane_captures=options.get("pane_captures"),
    )
    attention, attention_source = read_needs_attention(command=needs_command)
    if attention is None:
        attention = jsonio.as_object(value=snapshot_source.get("embedded_needs_attention"))
    release_item, release_source = release_lane_payload(
        repo=repo_path,
        options=options,
        measured_at=generated_at,
    )
    if attention is None and release_source is not None:
        empty_attention: dict[str, object] = {"items": []}
        attention = empty_attention
    attention = attention_with_release_lane(attention=attention, item=release_item)
    journal_records, journal_source = read_journal(
        path=option_journal_path(repo=repo_path, options=options),
        limit=option_journal_limit(options=options),
    )
    sources = {
        "snapshot": snapshot_source,
        "needs_attention": attention_source,
        "dispatch_journal": journal_source,
    }
    if release_source is not None:
        sources["release_lane"] = release_source
    return {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "repo": str(repo_path),
        "sources": sources,
        "snapshot": snapshot,
        "needs_attention": attention,
        "dispatch_journal": journal_records,
    }
