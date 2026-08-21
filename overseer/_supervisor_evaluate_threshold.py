"""Below-threshold idle branch for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_threshold
import registry
from _supervisor_config import DANGER_CTX_REMAINING
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "IdleThresholdDecision",
    "IdleThresholdRequest",
    "idle_threshold_decision",
]


@dataclass(frozen=True, kw_only=True)
class IdleThresholdDecision:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class IdleThresholdRequest:
    sup: Supervisor
    track: registry.Track
    obs: Observation
    session: str
    target: str
    threshold: int
    uncertifiable_ready: tuple[str, set[str]] | None
    note: str | None
    act: bool


def _apply_uncertifiable_ready(
    *,
    status: str,
    note: str | None,
    active_conditions: set[str],
    uncertifiable_ready: tuple[str, set[str]] | None,
) -> tuple[str, str | None]:
    if uncertifiable_ready is None:
        return status, note
    ready_note, ready_conditions = uncertifiable_ready
    active_conditions.update(ready_conditions)
    # A surfaced certification failure is its own report-only state.  In
    # particular, do not let a low context percentage relabel a deterministic
    # identity mismatch as ordinary ``danger``: that reads as a missed ready
    # declaration and hides the UUIDs needed to resolve it safely.
    return "ready-uncertifiable", ready_note


def idle_threshold_decision(*, request: IdleThresholdRequest) -> IdleThresholdDecision:
    active_conditions: set[str] = set()
    note = request.note
    expiry_notice_sent = False
    if request.act:
        expiry_notice_sent = _supervisor_threshold.maybe_send_expiry_notice(
            request=_supervisor_threshold.ThresholdRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                target=request.target,
                threshold=request.threshold,
                act=request.act,
                obs=request.obs,
            )
        )
    if expiry_notice_sent:
        danger = request.obs.eff_ctx is not None and request.obs.eff_ctx <= DANGER_CTX_REMAINING
        if danger:
            active_conditions.add("default")
        return IdleThresholdDecision(
            status="danger" if danger else "warned",
            note=note,
            active_conditions=active_conditions,
        )
    threshold_decision = _supervisor_threshold.threshold(
        request=_supervisor_threshold.ThresholdRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            target=request.target,
            threshold=request.threshold,
            act=request.act,
            obs=request.obs,
        )
    )
    status, note = _apply_uncertifiable_ready(
        status=threshold_decision.status,
        note=note,
        active_conditions=active_conditions,
        uncertifiable_ready=request.uncertifiable_ready,
    )
    active_conditions.update(threshold_decision.active_conditions)
    return IdleThresholdDecision(
        status=status,
        note=note,
        active_conditions=active_conditions,
    )
