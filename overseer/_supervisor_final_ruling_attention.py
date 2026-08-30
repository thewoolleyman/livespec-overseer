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
    "FinalRulingVerdict",
    "apply_final_ruling_attention",
]

FINAL_RULING_UNHEEDED_STATUS = "final-ruling-unheeded"
_BLOCKED_STATUSES = frozenset({"blocked:human", "picker-stalled", "pane-still"})
# A missing input must not render like a seat that never answered, so the
# unreadable case says so on both surfaces rather than sharing the silent text.
_LEDGER_UNAVAILABLE_QUALIFIER = "; ledger unreadable, movement unproven"


@dataclass(frozen=True, kw_only=True)
class FinalRulingResult:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class FinalRulingVerdict:
    """Whether the ruling went unheeded, and what the ledger was able to say."""

    unheeded: bool
    ledger_source: str


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


_HEEDED = FinalRulingVerdict(unheeded=False, ledger_source=ledger_comments.SOURCE_LEDGER)


def apply_final_ruling_attention(*, request: FinalRulingRequest) -> FinalRulingResult:
    relay = latest_final_relay(request=request)
    if relay is None:
        return _unchanged(request=request)
    exempt = _supervisor_final_ruling_sources.exemption_label(
        repo=Path(request.track.repo), item_id=relay.item_id, floor_at=relay.at
    )
    if exempt is not None:
        return _with_note(request=request, extra=f"final ruling exemption: {exempt}")
    verdict = final_ruling_verdict(request=request, relay=relay)
    if not verdict.unheeded:
        return _unchanged(request=request)

    age = max(0.0, request.sup.now() - relay.at)
    qualifier = (
        _LEDGER_UNAVAILABLE_QUALIFIER
        if verdict.ledger_source == ledger_comments.SOURCE_UNAVAILABLE
        else ""
    )
    note = _supervisor_liveness.append_note(
        note=request.note,
        extra=(
            "final ruling unheeded "
            f"{_supervisor_liveness.age_label(seconds=age)}{qualifier}; "
            "report-only, no restart authorized"
        ),
    )
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                f"final ruling unheeded - inspect that pane and its plan epic{qualifier}; "
                "report-only, no restart authorized"
            ),
            condition=FINAL_RULING_UNHEEDED_STATUS,
        )
    return FinalRulingResult(
        status=FINAL_RULING_UNHEEDED_STATUS,
        note=note,
        active_conditions={*request.active_conditions, FINAL_RULING_UNHEEDED_STATUS},
    )


def final_ruling_verdict(
    *, request: FinalRulingRequest, relay: _supervisor_final_ruling_sources.FinalRelay
) -> FinalRulingVerdict:
    """Whether the seat heeded the ruling, by either kind of movement.

    A moved branch settles it without reading the ledger at all: that read is a
    subprocess with a ten-second timeout, and the cheap evidence is conclusive.
    """
    if request.status not in _BLOCKED_STATUSES:
        return _HEEDED
    if request.sup.now() - relay.at < _supervisor_config.FINAL_RULING_UNHEEDED_AFTER:
        return _HEEDED
    repo = Path(request.track.repo)
    if _supervisor_final_ruling_sources.branch_moved(repo=repo, relay=relay):
        return _HEEDED
    movement = _supervisor_final_ruling_sources.ledger_comment_movement(repo=repo, relay=relay)
    if movement.moved:
        return _HEEDED
    return FinalRulingVerdict(unheeded=True, ledger_source=movement.source)


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
