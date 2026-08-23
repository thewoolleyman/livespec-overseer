"""Report-only attention for wait-premise targets that can no longer be found."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_liveness
import _supervisor_wait_target_sources
import registry
import wait_premises
from _supervisor_view import MAX_REASON_IN_ALERT, elide
from _supervisor_wait_target_status import (
    WAIT_TARGET_MISSING_CONDITION,
    WAIT_TARGET_MISSING_STATUS,
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


def _evidence_path(*, repo: Path, topic: str, key: str) -> Path:
    digest = sha256(key.encode("utf-8")).hexdigest()[:16]
    return repo / "tmp" / "overseer" / topic / f"wait-target-missing-{digest}.json"


def _requery_output(*, repo: Path, record: dict[str, object]) -> object:
    if _supervisor_wait_target_sources.local_record(
        record=record
    ) and not _supervisor_wait_target_sources.remote_record(record=record):
        return _supervisor_wait_target_sources.local_process_records(repo=repo)
    return _supervisor_wait_target_sources.read_journal(repo=repo)


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
    path = _evidence_path(repo=repo, topic=topic, key=key)
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


def _relay_text(
    *, record: dict[str, object], note: str, evidence_path: Path, evidence_source: str | None
) -> str:
    kind = _supervisor_wait_target_sources.string_field(record=record, key="kind") or "unknown"
    target_id = (
        _supervisor_wait_target_sources.string_field(record=record, key="target_id") or "unknown"
    )
    source = evidence_source or "unknown"
    return (
        "wait-target-missing evidence relay\n"
        f"premise: {kind} {target_id}\n"
        f"re-query: {source}\n"
        f"evidence record: {evidence_path}\n"
        f"result: {note}\n\n"
        "This delivers facts only. It does not choose your next action, does not "
        "authorize a restart, and does not change the ready-file interlock."
    )


def _relay_allowed(*, request: WaitTargetMissingRequest) -> bool:
    # `waiting` means "at a gate/prompt for the human" (_supervisor_observe), which
    # INCLUDES a picker-parked pane. Relaying there would choose the session's next
    # action, which this relay's floor forbids: it delivers FACTS only.
    return request.obs.claude_status == "waiting" and not request.obs.gate


def _deliver_relay(
    *,
    request: WaitTargetMissingRequest,
    record: dict[str, object],
    key: str,
    note: str,
    repo: Path,
) -> None:
    if key in request.obs.istate.wait_target_relayed_keys or not _relay_allowed(request=request):
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
    text = _relay_text(
        record=record, note=note, evidence_path=path, evidence_source=evidence_source
    )
    if not request.sup.tmux.bracketed_paste(session=request.pane, text=text):
        return
    if not request.sup.tmux.send_keys(session=request.pane, keys="Enter"):
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
