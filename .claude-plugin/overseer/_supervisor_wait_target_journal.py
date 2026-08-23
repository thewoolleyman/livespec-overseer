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


def dispatch_record_matches(
    *, record: dict[str, object], target_id: str, work_item_id: str | None
) -> bool:
    if record.get("stage") != "dispatch-id":
        return False
    if record.get("dispatch_id") != target_id:
        return False
    return work_item_id is None or record.get("work_item_id") == work_item_id


def outcome_run_id(
    *,
    record: dict[str, object],
    target_id: str,
    work_item_id: str | None,
    dispatch_at: str,
) -> str | None:
    if record.get("stage") != "outcome":
        return None
    if dispatch_at and (string_field(record=record, key="at") or "") <= dispatch_at:
        return None
    outcome = jsonio.as_object(value=record.get("outcome"))
    if outcome is None:
        return None
    if outcome.get("dispatch_id") != target_id:
        return None
    if work_item_id is not None and outcome.get("work_item_id") != work_item_id:
        return None
    return string_field(record=outcome, key="fabro_run_id")


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
) -> frozenset[str] | None:
    dispatch_at = ""
    found_dispatch = False
    for record in records:
        if not dispatch_record_matches(
            record=record, target_id=target_id, work_item_id=work_item_id
        ):
            continue
        found_dispatch = True
        dispatch_at = max(dispatch_at, string_field(record=record, key="at") or "")
    if not found_dispatch:
        return None

    run_ids: set[str] = set()
    for record in records:
        run_id = outcome_run_id(
            record=record,
            target_id=target_id,
            work_item_id=work_item_id,
            dispatch_at=dispatch_at,
        )
        if run_id is not None:
            run_ids.add(run_id)
    return frozenset(run_ids)
