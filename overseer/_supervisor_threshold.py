"""Below-threshold wrap-up branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_nudge
import _supervisor_observe
import _supervisor_restart
import _supervisor_threshold_expiry
import registry
import signals
from _supervisor_config import DANGER_CTX_REMAINING
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "ThresholdDecision",
    "ThresholdRequest",
    "maybe_send_expiry_notice",
    "threshold",
]


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
    threshold: int
    act: bool
    obs: Observation


def _fresh_threshold_observation(*, request: ThresholdRequest) -> Observation | None:
    """Re-read every paste authorization input immediately before opening a round."""
    return _supervisor_threshold_expiry.fresh_guarded_paste_observation(
        request=request, require_below_threshold=True
    )


maybe_send_expiry_notice = _supervisor_threshold_expiry.maybe_send_expiry_notice


def threshold(*, request: ThresholdRequest) -> ThresholdDecision:
    active_conditions: set[str] = set()
    _supervisor_threshold_expiry.close_round_if_no_longer_current(request=request)
    obs = request.obs
    eff_ctx = obs.eff_ctx if obs.eff_ctx is not None else request.threshold
    # A FRESH `winding-down` ACK buys patience: the session heard us and is
    # wrapping up, so stop re-warning (never keystroke into a session that is
    # actively winding down). A STALE ACK resumes escalating — an ACK must not
    # become an infinite stall — but still never authorizes an act.
    raw_ready = obs.declared is not None and obs.declared.token == signals.STATE_READY
    if request.act and not obs.acked and not obs.malformed and not raw_ready:
        fresh = _fresh_threshold_observation(request=request)
        if fresh is None:
            return ThresholdDecision(status="settling", active_conditions=active_conditions)
        obs = fresh
        eff_ctx = obs.eff_ctx if obs.eff_ctx is not None else eff_ctx
        _supervisor_restart.maybe_inject(
            sup=request.sup,
            track=request.track,
            target=request.target,
            eff_ctx=eff_ctx,
            threshold=request.threshold,
            is_codex=obs.is_codex,
        )
        _supervisor_observe.advance_condition(
            episode=obs.istate.winddown_starved_episode,
            condition_now=False,
            now=request.sup.now(),
        )
    if obs.acked:
        return ThresholdDecision(status="winding-down", active_conditions=active_conditions)
    if eff_ctx <= DANGER_CTX_REMAINING:
        active_conditions.add("danger-non-responder")
        # A standing ready has its own certification surface.  Calling it a
        # non-responder here is false (and conceals the real interlock reason).
        if request.act and not raw_ready:
            _supervisor_nudge.alert_non_responder(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.target,
                eff_ctx=eff_ctx,
                declared=obs.declared,
            )
        return ThresholdDecision(status="danger", active_conditions=active_conditions)
    return ThresholdDecision(status="warned", active_conditions=active_conditions)
