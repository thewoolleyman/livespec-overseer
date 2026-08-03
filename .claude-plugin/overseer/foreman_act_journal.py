"""Dispatch-journal triage validation for the foreman actuator."""

from __future__ import annotations

import sys
from pathlib import Path

import jsonio

__all__: list[str] = ["journal_reconcile_command"]


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None


def _int_field(*, payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):  # pragma: no cover
        return None
    return value


def _journal_source(*, document: dict[str, object]) -> dict[str, object] | None:
    sources = jsonio.as_object(value=document.get("sources"))
    if sources is None:  # pragma: no cover
        return None
    return jsonio.as_object(value=sources.get("dispatch_journal"))


def _journal_records(*, document: dict[str, object]) -> list[dict[str, object]] | None:
    raw = jsonio.as_list(value=document.get("dispatch_journal"))
    if raw is None:  # pragma: no cover
        return None
    records: list[dict[str, object]] = []
    for item in raw:
        record = jsonio.as_object(value=item)
        if record is None:  # pragma: no cover
            return None
        records.append(record)
    return records


def _proposal_record(*, proposal: dict[str, object]) -> dict[str, object] | None:
    payload = jsonio.as_object(value=proposal.get("dispatch_journal"))
    if payload is None:  # pragma: no cover
        return None
    return jsonio.as_object(value=payload.get("record"))


def _proposal_records_read(*, proposal: dict[str, object]) -> int | None:
    payload = jsonio.as_object(value=proposal.get("dispatch_journal"))
    if payload is None:  # pragma: no cover
        return None
    return _int_field(payload=payload, key="records_read")


def _dispatcher_path(*, proposal: dict[str, object]) -> Path | None:
    payload = jsonio.as_object(value=proposal.get("dispatcher"))
    if payload is None:  # pragma: no cover
        return None
    value = _str_field(payload=payload, key="path")
    if value is None:  # pragma: no cover
        return None
    path = Path(value)
    if (  # pragma: no cover
        not path.is_absolute() or path.name != "dispatcher.py" or not path.is_file()
    ):
        return None
    return path


def _outcome(*, record: dict[str, object]) -> dict[str, object] | None:
    if record.get("stage") != "outcome":  # pragma: no cover
        return None
    return jsonio.as_object(value=record.get("outcome"))


def _qualifying_work_item(*, record: dict[str, object]) -> str | None:
    outcome = _outcome(record=record)
    if outcome is None:  # pragma: no cover
        return None
    work_item_id = _str_field(payload=outcome, key="work_item_id")
    status = _str_field(payload=outcome, key="status")
    stage = _str_field(payload=outcome, key="stage")
    pr_number = _int_field(payload=outcome, key="pr_number")
    merge_sha = _str_field(payload=outcome, key="merge_sha")
    if (
        work_item_id is None
        or status != "failed"
        or stage is None
        or pr_number is None
        or merge_sha is None
    ):  # pragma: no cover
        return None
    return work_item_id


def _matching_qualified_records(
    *, records: list[dict[str, object]], work_item_id: str
) -> list[dict[str, object]]:
    return [record for record in records if _qualifying_work_item(record=record) == work_item_id]


def _validated_reconcile(
    *, proposal: dict[str, object], document: dict[str, object]
) -> tuple[str | None, str | None]:
    proposed_record = _proposal_record(proposal=proposal)
    records = _journal_records(document=document)
    if records is None or proposed_record is None:  # pragma: no cover
        return "malformed_dispatch_journal", None
    work_item_id = _qualifying_work_item(record=proposed_record)
    if work_item_id is None:
        return "unsupported_transition", None
    generation_refusal = _validate_generation(proposal=proposal, document=document)
    if proposed_record not in records:
        return generation_refusal or "journal_record_changed", None
    matches = _matching_qualified_records(records=records, work_item_id=work_item_id)
    if len(matches) != 1:
        return "ambiguous_dispatch_claim", None
    return generation_refusal, work_item_id


def _validate_generation(*, proposal: dict[str, object], document: dict[str, object]) -> str | None:
    source = _journal_source(document=document)
    expected_records_read = _proposal_records_read(proposal=proposal)
    if source is None or expected_records_read is None:  # pragma: no cover
        return "malformed_dispatch_journal"
    current_records_read = _int_field(payload=source, key="records_read")
    if source.get("status") != "ok" or current_records_read is None:  # pragma: no cover
        return "dispatch_journal_not_actable"
    if current_records_read != expected_records_read:
        return "journal_generation_changed"
    return None


def journal_reconcile_command(
    *, proposal: dict[str, object], document: dict[str, object], repo: str
) -> tuple[str | None, list[str] | None]:
    refusal, work_item_id = _validated_reconcile(proposal=proposal, document=document)
    if refusal is not None or work_item_id is None:
        return refusal, None
    dispatcher = _dispatcher_path(proposal=proposal)
    if dispatcher is None:  # pragma: no cover
        return "malformed_dispatcher", None
    return None, [
        sys.executable,
        str(dispatcher),
        "reconcile-merged",
        "--repo",
        repo,
        "--item",
        work_item_id,
        "--json",
    ]
