# livespec-lloc-soft-band-owner: overseer-hgq4wi.6
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


def _forge_merged_pull_request(*, proposal: dict[str, object]) -> dict[str, object] | None:
    forge = jsonio.as_object(value=proposal.get("forge"))
    if forge is None:
        return None
    return jsonio.as_object(value=forge.get("merged_pull_request"))


def _forge_head_ref(*, proposal: dict[str, object]) -> str | None:
    pull_request = _forge_merged_pull_request(proposal=proposal)
    if pull_request is None:  # pragma: no cover
        return None
    return _str_field(payload=pull_request, key="head_ref")


def _published_by_dispatcher(*, outcome: dict[str, object]) -> bool:
    return (
        _int_field(payload=outcome, key="pr_number") is not None
        and _str_field(payload=outcome, key="merge_sha") is not None
    )


def _host_published_by_forge(*, outcome: dict[str, object], proposal: dict[str, object]) -> bool:
    pull_request = _forge_merged_pull_request(proposal=proposal)
    if pull_request is None:  # pragma: no cover
        return False
    branch = _str_field(payload=outcome, key="publish_branch")
    return (
        _int_field(payload=pull_request, key="number") is not None
        and _str_field(payload=pull_request, key="merge_sha") is not None
        and branch is not None
        and _forge_head_ref(proposal=proposal) == branch
    )


def _host_publish_trace_refusal(
    *, record: dict[str, object], proposal: dict[str, object]
) -> str | None:
    outcome = _outcome(record=record)
    if outcome is None:  # pragma: no cover
        return None
    if _published_by_dispatcher(outcome=outcome):  # pragma: no cover
        return None
    branch = _str_field(payload=outcome, key="publish_branch")
    if branch is None or _forge_merged_pull_request(proposal=proposal) is None:  # pragma: no cover
        return None
    if _forge_head_ref(proposal=proposal) != branch:
        return "forge_evidence_not_traced_to_dispatch"
    return None  # pragma: no cover


def _qualifying_work_item(*, record: dict[str, object], proposal: dict[str, object]) -> str | None:
    outcome = _outcome(record=record)
    if outcome is None:  # pragma: no cover
        return None
    work_item_id = _str_field(payload=outcome, key="work_item_id")
    status = _str_field(payload=outcome, key="status")
    stage = _str_field(payload=outcome, key="stage")
    if (
        work_item_id is None
        or status != "failed"
        or stage is None
        or not (
            _published_by_dispatcher(outcome=outcome)
            or _host_published_by_forge(outcome=outcome, proposal=proposal)
        )
    ):  # pragma: no cover
        return None
    return work_item_id


def _matching_qualified_records(
    *, records: list[dict[str, object]], work_item_id: str, proposal: dict[str, object]
) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if _qualifying_work_item(record=record, proposal=proposal) == work_item_id
    ]


def _claim_abandonment_reason(
    *, record: dict[str, object], proposal: dict[str, object]
) -> str | None:
    if record.get("stage") != "dispatch-claim-abandoned":  # pragma: no cover
        return None
    if _str_field(payload=record, key="reason") != "non_green_terminal_outcome":
        return None
    work_item_id = _str_field(payload=record, key="work_item_id")
    if work_item_id is None:  # pragma: no cover
        return None
    if _forge_merged_pull_request(proposal=proposal) is None:  # pragma: no cover
        return None
    return "dispatcher_saw_no_green_outcome"


def _ambiguous_or_traced(
    *,
    matches: list[dict[str, object]],
    proposed_record: dict[str, object],
    proposal: dict[str, object],
) -> str | None:
    if len(matches) == 1:
        return None
    if _forge_merged_pull_request(proposal=proposal) is None:
        return "ambiguous_dispatch_claim"
    proposed_outcome = _outcome(record=proposed_record)
    branch = (
        None
        if proposed_outcome is None
        else _str_field(payload=proposed_outcome, key="publish_branch")
    )
    if branch is None or _forge_head_ref(proposal=proposal) != branch:  # pragma: no cover
        return "forge_evidence_not_traced_to_dispatch"
    for record in matches:
        outcome = _outcome(record=record)
        if (
            outcome is None or _str_field(payload=outcome, key="publish_branch") != branch
        ):  # pragma: no cover
            return "ambiguous_dispatch_claim"
    return None


def _unsupported_refusal(*, record: dict[str, object], proposal: dict[str, object]) -> str:
    trace_refusal = _host_publish_trace_refusal(record=record, proposal=proposal)
    if trace_refusal is not None:
        return trace_refusal
    abandonment_reason = _claim_abandonment_reason(record=record, proposal=proposal)
    if abandonment_reason is not None:
        return abandonment_reason
    return "unsupported_transition"


def _validated_reconcile(
    *, proposal: dict[str, object], document: dict[str, object]
) -> tuple[str | None, str | None]:
    proposed_record = _proposal_record(proposal=proposal)
    records = _journal_records(document=document)
    if records is None or proposed_record is None:  # pragma: no cover
        return "malformed_dispatch_journal", None
    work_item_id = _qualifying_work_item(record=proposed_record, proposal=proposal)
    if work_item_id is None:
        return _unsupported_refusal(record=proposed_record, proposal=proposal), None
    generation_refusal = _validate_generation(proposal=proposal, document=document)
    if proposed_record not in records:
        return generation_refusal or "journal_record_changed", None
    matches = _matching_qualified_records(
        records=records, work_item_id=work_item_id, proposal=proposal
    )
    ambiguity_refusal = _ambiguous_or_traced(
        matches=matches, proposed_record=proposed_record, proposal=proposal
    )
    if ambiguity_refusal is not None:
        return ambiguity_refusal, None
    return generation_refusal, work_item_id


def _validate_generation(*, proposal: dict[str, object], document: dict[str, object]) -> str | None:
    source = _journal_source(document=document)
    expected_records_read = _proposal_records_read(proposal=proposal)
    if source is None or expected_records_read is None:  # pragma: no cover
        return "malformed_dispatch_journal"
    current_records_read = _int_field(payload=source, key="records_read")
    if source.get("status") != "ok" or current_records_read is None:  # pragma: no cover
        return "dispatch_journal_not_actable"
    if _forge_merged_pull_request(proposal=proposal) is not None:
        if current_records_read < expected_records_read:  # pragma: no cover
            return "journal_generation_changed"
        return None
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
