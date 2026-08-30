"""Evidence records for wait-premise targets that can no longer be found.

An evidence record carries the premise itself plus the authoritative source
re-queried and SCOPED to that premise's own target, so an operator reading the
record sees what the daemon saw rather than taking the verdict on trust. The
lifecycle also writes one before it removes a premise from disk, which is what
keeps a cleared premise auditable after cleanup.
"""

from __future__ import annotations

import json
from pathlib import Path

import _supervisor_wait_target_lifecycle
import _supervisor_wait_target_sources
import jsonio

__all__: list[str] = ["write_evidence"]


def _requery_output(*, repo: Path, record: dict[str, object]) -> object:
    target_id = _supervisor_wait_target_sources.string_field(record=record, key="target_id")
    work_item_id = _supervisor_wait_target_sources.string_field(record=record, key="work_item_id")
    target = target_id or ""
    if _supervisor_wait_target_sources.local_record(
        record=record
    ) and not _supervisor_wait_target_sources.remote_record(record=record):
        return _local_requery_records(
            records=_supervisor_wait_target_sources.local_process_records(repo=repo),
            target_id=target,
            work_item_id=work_item_id,
        )
    return _journal_requery_records(
        records=_supervisor_wait_target_sources.read_journal(repo=repo),
        target_id=target,
        work_item_id=work_item_id,
    )


def _work_item_matches(*, record: dict[str, object], work_item_id: str | None) -> bool:
    record_work_item = _supervisor_wait_target_sources.string_field(
        record=record, key="work_item_id"
    )
    return record_work_item is None or work_item_id is None or record_work_item == work_item_id


def _local_requery_records(
    *, records: list[dict[str, object]], target_id: str, work_item_id: str | None
) -> list[dict[str, object]]:
    return [
        item
        for item in records
        if _supervisor_wait_target_sources.record_id(record=item) == target_id
        and _work_item_matches(record=item, work_item_id=work_item_id)
    ]


def _journal_dispatch_matches(
    *, record: dict[str, object], target_id: str, work_item_id: str | None
) -> bool:
    if record.get("stage") != "dispatch-id":
        return False
    if record.get("dispatch_id") != target_id and record.get("run_id") != target_id:
        return False
    return _work_item_matches(record=record, work_item_id=work_item_id)


def _journal_outcome_matches(
    *, record: dict[str, object], target_id: str, work_item_id: str | None
) -> bool:
    if record.get("stage") != "outcome":
        return False
    outcome = record.get("outcome")
    outcome_record = jsonio.as_object(value=outcome)
    if outcome_record is None:
        return False
    if outcome_record.get("dispatch_id") != target_id and outcome_record.get("run_id") != target_id:
        return False
    return _work_item_matches(record=outcome_record, work_item_id=work_item_id)


def _journal_requery_records(
    *, records: list[dict[str, object]], target_id: str, work_item_id: str | None
) -> list[dict[str, object]]:
    return [
        item
        for item in records
        if _journal_dispatch_matches(record=item, target_id=target_id, work_item_id=work_item_id)
        or _journal_outcome_matches(record=item, target_id=target_id, work_item_id=work_item_id)
    ]


def _evidence_record(
    *, repo: Path, record: dict[str, object], status: str, note: str
) -> dict[str, object]:
    return {
        "evidence_source": _supervisor_wait_target_sources.string_field(
            record=record, key="evidence_source"
        ),
        "note": note,
        "premise": record,
        "requery_output": _requery_output(repo=repo, record=record),
        "status": status,
        "target_id": _supervisor_wait_target_sources.string_field(record=record, key="target_id"),
    }


def write_evidence(
    *, repo: Path, topic: str, key: str, record: dict[str, object], status: str, note: str
) -> Path | None:
    path = _supervisor_wait_target_lifecycle.evidence_path(repo=repo, topic=topic, key=key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(
            json.dumps(
                _evidence_record(repo=repo, record=record, status=status, note=note),
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        return None
    return path
