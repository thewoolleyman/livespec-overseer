"""Filesystem persistence helpers for bounded foreman work-item sessions."""

from __future__ import annotations

import json
from pathlib import Path

import jsonio
import registry

__all__: list[str] = [
    "append_event",
    "handoff_paths",
    "read_json",
    "state_dir",
    "write_handoff",
    "write_json",
]


def state_dir(*, repo: Path, work_item_id: str) -> Path:
    return repo / "tmp" / "overseer" / "foreman" / "work-items" / work_item_id


def read_json(*, path: Path) -> dict[str, object] | None:
    try:
        parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()


def write_json(*, path: Path, payload: dict[str, object]) -> None:
    registry.atomic_write(path=path, body=json.dumps(payload, indent=2, sort_keys=True) + "\n")


def append_event(*, directory: Path, record: dict[str, object]) -> None:
    path = directory / "journal.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        _ = handle.write(json.dumps(record, sort_keys=True) + "\n")


def handoff_paths(*, repo: Path, work_item_id: str) -> tuple[Path, Path]:
    directory = state_dir(repo=repo, work_item_id=work_item_id)
    return directory / "handoff.md", directory / "handoff.json"


def write_handoff(*, repo: Path, payload: dict[str, object]) -> Path | None:
    content = _str_field(payload=payload, key="handoff")
    work_item_id = _str_field(payload=payload, key="work_item_id")
    if content is None or work_item_id is None:
        return None
    handoff, meta = handoff_paths(repo=repo, work_item_id=work_item_id)
    registry.atomic_write(path=handoff, body=content)
    write_json(path=meta, payload={"work_item_id": work_item_id, "path": str(handoff)})
    return handoff


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None
