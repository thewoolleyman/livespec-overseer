"""Dispatch-journal bridge for remote wait-target liveness."""

from __future__ import annotations

from pathlib import Path

import jsonio

__all__: list[str] = [
    "journal_run_ids",
    "read_journal",
]

_JOURNAL = Path("tmp") / "fabro-dispatch-journal.jsonl"


def string_field(*, record: dict[str, object], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def read_journal(*, repo: Path) -> list[dict[str, object]]:
    try:
        lines = (repo / _JOURNAL).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict[str, object]] = []
    for line in lines:
        parsed = jsonio.parse_object_line(line=line)
        if jsonio.is_parse_failure(result=parsed):
            continue
        record = parsed.unwrap()
        if record is not None:
            records.append(record)
    return records


def journal_run_ids(
    *, records: list[dict[str, object]], target_id: str, work_item_id: str | None
) -> frozenset[str]:
    run_ids: set[str] = set()
    for record in records:
        if record.get("stage") != "dispatch-id":
            continue
        if record.get("dispatch_id") != target_id:
            continue
        if work_item_id is not None and record.get("work_item_id") != work_item_id:
            continue
        run_id = string_field(record=record, key="run_id")
        if run_id is not None:
            run_ids.add(run_id)
    return frozenset(run_ids)
