"""Escalation-exhausted attention predicate and continuity floor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_observe
import registry
import signals
from _supervisor_config import ESCALATION_EXHAUSTED_AFTER
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "EscalationExhaustion",
    "ObserveEscalationExhaustionRequest",
    "observe_escalation_exhaustion",
]


@dataclass(frozen=True, kw_only=True)
class EscalationExhaustion:
    active_now: bool
    due: bool
    age: float | None


@dataclass(frozen=True, kw_only=True)
class ObserveEscalationExhaustionRequest:
    sup: Supervisor
    track: registry.Track
    istate: InjectState
    eff_ctx: int | None
    threshold: int
    idle: bool
    busy: bool
    generating: bool
    shell_only: bool
    declared: signals.TrackState | None
    round_record: registry.RoundRecord


def _escalation_bands(*, threshold: int) -> set[int]:
    return {threshold} | {band for band in (40, 30, 20, 10) if band < threshold}


def _notified_through_context(*, request: ObserveEscalationExhaustionRequest, eff_ctx: int) -> bool:
    notified = set(
        registry.read_notified_bands(
            repo=request.track.repo,
            topic=request.track.topic,
            stamp_path=request.sup.stamp_path,
        )
    )
    return all(
        band in notified
        for band in _escalation_bands(threshold=request.threshold)
        if band >= eff_ctx
    )


def _no_session_declaration(*, declared: signals.TrackState | None) -> bool:
    return declared is None or declared.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT


def _active_now(*, request: ObserveEscalationExhaustionRequest) -> bool:
    return (
        request.round_record.at is not None
        and request.round_record.malformed_reason is None
        and request.eff_ctx is not None
        and request.eff_ctx <= request.threshold
        and _notified_through_context(request=request, eff_ctx=request.eff_ctx)
        and _no_session_declaration(declared=request.declared)
        and not registry.read_resume_pending(
            repo=request.track.repo,
            topic=request.track.topic,
            stamp_path=request.sup.stamp_path,
        )
        and request.idle
        and not request.busy
        and not request.generating
        and not request.shell_only
    )


def observe_escalation_exhaustion(
    *, request: ObserveEscalationExhaustionRequest
) -> EscalationExhaustion:
    now = request.sup.now()
    active_now = _active_now(request=request)
    _supervisor_observe.advance_condition(
        episode=request.istate.escalation_exhausted_episode,
        condition_now=active_now,
        now=now,
    )
    age = (
        now - request.istate.escalation_exhausted_episode.since
        if request.istate.escalation_exhausted_episode.since is not None
        else None
    )
    return EscalationExhaustion(
        active_now=active_now,
        due=age is not None and age >= ESCALATION_EXHAUSTED_AFTER,
        age=age,
    )
