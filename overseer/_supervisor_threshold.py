"""Below-threshold wrap-up branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_nudge
import _supervisor_observe
import _supervisor_restart
import registry
import signals
from _supervisor_config import DANGER_CTX_REMAINING
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["ThresholdDecision", "ThresholdRequest", "threshold"]


@dataclass(frozen=True, kw_only=True)
class ThresholdDecision:
    status: str
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class ThresholdRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    target: str
    eff_ctx: int
    threshold: int
    acked: bool
    declared: signals.TrackState | None
    act: bool
    is_codex: bool
    istate: InjectState


def threshold(*, request: ThresholdRequest) -> ThresholdDecision:
    active_conditions: set[str] = set()
    if request.act and not request.acked:
        _supervisor_restart.maybe_inject(
            sup=request.sup,
            track=request.track,
            target=request.target,
            eff_ctx=request.eff_ctx,
            threshold=request.threshold,
            is_codex=request.is_codex,
        )
        _supervisor_observe.advance_condition(
            episode=request.istate.winddown_starved_episode,
            condition_now=False,
            now=request.sup.now(),
        )
    if request.acked:
        return ThresholdDecision(status="winding-down", active_conditions=active_conditions)
    if request.eff_ctx <= DANGER_CTX_REMAINING:
        active_conditions.add("default")
        if request.act:
            _supervisor_nudge.alert_non_responder(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.target,
                eff_ctx=request.eff_ctx,
                declared=request.declared,
            )
        return ThresholdDecision(status="danger", active_conditions=active_conditions)
    return ThresholdDecision(status="warned", active_conditions=active_conditions)
