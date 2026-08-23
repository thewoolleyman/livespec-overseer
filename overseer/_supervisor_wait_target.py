"""Report-only attention for wait-premise targets that can no longer be found."""
# livespec-lloc-soft-band-owner: overseer-1a31.2.1

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_liveness
import _supervisor_wait_target_lifecycle
import _supervisor_wait_target_sources
import jsonio
import registry
import wait_premises
from _supervisor_view import MAX_REASON_IN_ALERT, elide
from _supervisor_wait_target_status import (
    WAIT_TARGET_EXPIRED_STATUS,
    WAIT_TARGET_MISSING_CONDITION,
    WAIT_TARGET_MISSING_STATUS,
    WAIT_TARGET_SATISFIED_STATUS,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "WAIT_TARGET_MISSING_CONDITION",
    "WAIT_TARGET_MISSING_STATUS",
    "WaitTargetMissingRequest",
    "WaitTargetMissingResult",
    "apply_wait_target_missing_attention",
]


@dataclass(frozen=True, kw_only=True)
class WaitTargetMissingResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class WaitTargetMissingRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def _unchanged(*, request: WaitTargetMissingRequest) -> WaitTargetMissingResult:
    return WaitTargetMissingResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _surface(*, request: WaitTargetMissingRequest, note: str) -> None:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"{elide(text=note, limit=MAX_REASON_IN_ALERT)} - inspect the waiting "
            "session; report-only, no restart authorized"
        ),
        condition=WAIT_TARGET_MISSING_CONDITION,
    )


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


def _write_evidence(
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


def _deliver_relay(
    *,
    request: WaitTargetMissingRequest,
    record: dict[str, object],
    key: str,
    note: str,
    repo: Path,
) -> None:
    if (
        key in request.obs.istate.wait_target_relayed_keys
        or not _supervisor_wait_target_lifecycle.relay_allowed(
            idle=request.obs.idle, busy=request.obs.busy, gate=request.obs.gate
        )
    ):
        return
    evidence_source = _supervisor_wait_target_sources.string_field(
        record=record, key="evidence_source"
    )
    path = _write_evidence(
        repo=repo,
        topic=request.track.topic,
        key=key,
        record=record,
        status=WAIT_TARGET_MISSING_STATUS,
        note=note,
    )
    if path is None:
        return
    text = _supervisor_wait_target_lifecycle.relay_text(
        record=record, note=note, evidence_path=path, evidence_source=evidence_source
    )
    if not _supervisor_launch.submit_prompt(
        sup=request.sup, target=request.pane, text=text, expect_codex=request.obs.is_codex
    ):
        return
    request.obs.istate.wait_target_relayed_keys.add(key)


def apply_wait_target_missing_attention(
    *, request: WaitTargetMissingRequest
) -> WaitTargetMissingResult:
    records = wait_premises.read_wait_premises(repo=request.track.repo, topic=request.track.topic)
    if not records:
        return _unchanged(request=request)
    repo = Path(request.track.repo)
    now = request.obs.observed_at
    cache = request.obs.istate.wait_target_cache
    for record in records:
        key = _supervisor_wait_target_sources.cache_key(record=record)
        entry = _supervisor_wait_target_sources.verify_wait_target_record(
            repo=repo, record=record, cache=cache.get(key), now=now
        )
        cache[key] = entry
        if entry.status == WAIT_TARGET_SATISFIED_STATUS:
            request.obs.istate.wait_target_relayed_keys.discard(key)
            _supervisor_wait_target_lifecycle.clear_premise_with_evidence(
                repo=repo,
                topic=request.track.topic,
                record=record,
                key=key,
                status=WAIT_TARGET_SATISFIED_STATUS,
                write_evidence=_write_evidence,
            )
            continue
        if (
            entry.status == WAIT_TARGET_MISSING_STATUS
            and _supervisor_wait_target_lifecycle.expired_and_no_longer_waiting(
                status=request.status, observed_at=request.obs.observed_at, record=record
            )
        ):
            request.obs.istate.wait_target_relayed_keys.discard(key)
            _supervisor_wait_target_lifecycle.clear_premise_with_evidence(
                repo=repo,
                topic=request.track.topic,
                record=record,
                key=key,
                status=WAIT_TARGET_EXPIRED_STATUS,
                write_evidence=_write_evidence,
            )
            continue
        if entry.status != WAIT_TARGET_MISSING_STATUS or entry.note is None:
            request.obs.istate.wait_target_relayed_keys.discard(key)
            continue
        note = _supervisor_liveness.append_note(note=request.note, extra=entry.note)
        if request.act:  # pragma: no branch
            _surface(request=request, note=entry.note)
            _deliver_relay(
                request=request,
                record=record,
                key=key,
                note=entry.note,
                repo=repo,
            )
        return WaitTargetMissingResult(
            status=WAIT_TARGET_MISSING_STATUS,
            note=note,
            active_conditions={*request.active_conditions, WAIT_TARGET_MISSING_CONDITION},
        )
    return _unchanged(request=request)
