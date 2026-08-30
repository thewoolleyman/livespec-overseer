"""Report-only attention for final foreman rulings a worker has not heeded."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_config
import _supervisor_final_ruling_sources
import _supervisor_liveness
import ledger_comments
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "FINAL_RULING_UNHEEDED_STATUS",
    "FinalRulingRequest",
    "FinalRulingResult",
    "apply_final_ruling_attention",
]

FINAL_RULING_UNHEEDED_STATUS = "final-ruling-unheeded"
_BLOCKED_STATUSES = frozenset({"blocked:human", "picker-stalled", "pane-still"})
# An unread ledger and a read-but-silent seat are BOTH unheeded, and the
# operator's next move differs: one is a seat to inspect, the other is a source
# to repair. Naming the uncertainty keeps them from rendering identically.
_LEDGER_UNREADABLE = "ledger unreadable, so the seat's answer is unverified; "


@dataclass(frozen=True, kw_only=True)
class FinalRulingResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class FinalRulingRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def apply_final_ruling_attention(*, request: FinalRulingRequest) -> FinalRulingResult:
    relay = latest_final_relay(request=request)
    if relay is None:
        return _unchanged(request=request)
    exempt = _supervisor_final_ruling_sources.exemption_label(
        repo=Path(request.track.repo), item_id=relay.item_id, floor_at=relay.at
    )
    if exempt is not None:
        return _with_note(request=request, extra=f"final ruling exemption: {exempt}")
    answer = final_ruling_unheeded(request=request, relay=relay)
    if answer is None:
        return _unchanged(request=request)

    age = max(0.0, request.sup.now() - relay.at)
    qualifier = _ledger_qualifier(answer=answer)
    note = _supervisor_liveness.append_note(
        note=request.note,
        extra=(
            f"final ruling unheeded {_supervisor_liveness.age_label(seconds=age)}; "
            f"{qualifier}report-only, no restart authorized"
        ),
    )
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                "final ruling unheeded - inspect that pane and its plan epic; "
                f"{qualifier}report-only, no restart authorized"
            ),
            condition=FINAL_RULING_UNHEEDED_STATUS,
        )
    return FinalRulingResult(
        status=FINAL_RULING_UNHEEDED_STATUS,
        note=note,
        active_conditions={*request.active_conditions, FINAL_RULING_UNHEEDED_STATUS},
    )


def final_ruling_unheeded(
    *, request: FinalRulingRequest, relay: _supervisor_final_ruling_sources.FinalRelay
) -> _supervisor_final_ruling_sources.LedgerAnswer | None:
    """The seat's ledger answer when the ruling stands unheeded, else None.

    Answering the LedgerAnswer rather than a bare bool is what carries the
    unreadable-ledger case out to the surfaces: an unread ledger and a silent
    seat both leave the ruling unheeded, and the operator needs to know which.
    """
    if request.status not in _BLOCKED_STATUSES:
        return None
    if request.sup.now() - relay.at < _supervisor_config.FINAL_RULING_UNHEEDED_AFTER:
        return None
    repo = Path(request.track.repo)
    if _supervisor_final_ruling_sources.branch_moved(repo=repo, relay=relay):
        return None
    answer = _supervisor_final_ruling_sources.ledger_comment_moved(repo=repo, relay=relay)
    return None if answer.moved else answer


def latest_final_relay(
    *, request: FinalRulingRequest
) -> _supervisor_final_ruling_sources.FinalRelay | None:
    records = _supervisor_final_ruling_sources.read_journal(repo=Path(request.track.repo))
    if records is None:
        return None
    relays = tuple(
        relay
        for record in records
        if (
            relay := _supervisor_final_ruling_sources.relay_from_record(
                record=record,
                fallback_item_id=request.track.epic,
            )
        )
        is not None
        and relay.item_id == request.track.epic
    )
    if not relays:
        return None
    return max(relays, key=lambda relay: relay.at)


def _ledger_qualifier(*, answer: _supervisor_final_ruling_sources.LedgerAnswer) -> str:
    if answer.source == ledger_comments.SOURCE_UNAVAILABLE:
        return _LEDGER_UNREADABLE
    return ""


def _unchanged(*, request: FinalRulingRequest) -> FinalRulingResult:
    return FinalRulingResult(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )


def _with_note(*, request: FinalRulingRequest, extra: str) -> FinalRulingResult:
    return FinalRulingResult(
        status=request.status,
        note=_supervisor_liveness.append_note(note=request.note, extra=extra),
        active_conditions=set(request.active_conditions),
    )
