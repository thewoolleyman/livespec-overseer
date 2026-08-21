"""Observe liveness attention inputs before attention decisions are made."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention_exhausted
import _supervisor_observe
import _supervisor_supervisor_state
import registry
import signals
from _supervisor_config import SHELL_PROLONGED_AFTER, WINDDOWN_STARVED_AFTER
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "LivenessAttention",
    "ObserveRequest",
    "observe_liveness_attention",
]


@dataclass(frozen=True, kw_only=True)
class LivenessAttention:
    generating: bool
    shell_only: bool
    escalation_exhausted_now: bool
    escalation_exhausted_due: bool
    starving_now: bool
    starved_due: bool
    shell_due: bool
    escalation_exhausted_age: float | None
    starvation_age: float | None
    shell_age: float | None
    supervisor_state_stale: bool = False
    supervisor_state_age: float | None = None
    supervisor_state_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ObserveRequest:
    sup: Supervisor
    track: registry.Track
    istate: InjectState
    capture: str
    claude_status: str | None
    codex_fallback: bool
    eff_ctx: int | None
    threshold: int
    injection_stamp: float | None
    idle: bool
    busy: bool
    declared: signals.TrackState | None
    round_record: registry.RoundRecord


def observe_liveness_attention(*, request: ObserveRequest) -> LivenessAttention:
    generating = signals.is_busy(capture_text=request.capture) or request.claude_status == "busy"
    shell_only = (not signals.is_busy(capture_text=request.capture)) and (
        request.claude_status == "shell" or request.codex_fallback
    )
    now = request.sup.now()
    escalation_exhaustion = _supervisor_attention_exhausted.observe_escalation_exhaustion(
        request=_supervisor_attention_exhausted.ObserveEscalationExhaustionRequest(
            sup=request.sup,
            track=request.track,
            istate=request.istate,
            eff_ctx=request.eff_ctx,
            threshold=request.threshold,
            idle=request.idle,
            busy=request.busy,
            generating=generating,
            shell_only=shell_only,
            declared=request.declared,
            round_record=request.round_record,
        )
    )
    supervisor_state = _supervisor_supervisor_state.observe_supervisor_state_freshness(
        sup=request.sup, track=request.track
    )
    starving_now = (
        request.eff_ctx is not None
        and request.eff_ctx <= request.threshold
        and request.injection_stamp is None
    )
    _supervisor_observe.advance_condition(
        episode=request.istate.winddown_starved_episode, condition_now=starving_now, now=now
    )
    _supervisor_observe.advance_condition(
        episode=request.istate.shell_episode, condition_now=shell_only, now=now
    )
    starvation_age = (
        now - request.istate.winddown_starved_episode.since
        if request.istate.winddown_starved_episode.since is not None
        else None
    )
    shell_age = (
        now - request.istate.shell_episode.since
        if request.istate.shell_episode.since is not None
        else None
    )
    return LivenessAttention(
        generating=generating,
        shell_only=shell_only,
        escalation_exhausted_now=escalation_exhaustion.active_now,
        escalation_exhausted_due=escalation_exhaustion.due,
        starving_now=starving_now,
        starved_due=starvation_age is not None and starvation_age >= WINDDOWN_STARVED_AFTER,
        shell_due=shell_age is not None and shell_age >= SHELL_PROLONGED_AFTER,
        supervisor_state_stale=supervisor_state.stale,
        escalation_exhausted_age=escalation_exhaustion.age,
        starvation_age=starvation_age,
        shell_age=shell_age,
        supervisor_state_age=supervisor_state.age,
        supervisor_state_reason=supervisor_state.reason,
    )
