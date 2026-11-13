"""Adapt retained-wrap-up retry to the evaluator's idle branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_pending_wrapup

if TYPE_CHECKING:
    from _supervisor_evaluate_idle import IdleRequest

__all__: list[str] = ["PendingIdleDecision", "retry"]


@dataclass(frozen=True, kw_only=True)
class PendingIdleDecision:
    status: str
    active_conditions: set[str]


def retry(*, request: IdleRequest) -> PendingIdleDecision | None:
    """Return an idle-branch override when a retained wrap-up handled this tick."""
    decision = _supervisor_pending_wrapup.retry_decision(
        sup=request.sup,
        track=request.track,
        obs=request.obs,
        session=request.session,
        target=request.target,
        act=request.act,
    )
    if decision is None or decision.status is None:
        return None
    return PendingIdleDecision(
        status=decision.status,
        active_conditions=decision.active_conditions,
    )
