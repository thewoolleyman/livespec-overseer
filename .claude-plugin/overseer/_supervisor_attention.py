"""Report-only liveness attention for shell and wind-down starvation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_supervisor_state
import registry
from _supervisor_attention_alerts import (
    EscalationExhaustedAlertRequest,
    ShellAlertRequest,
    StarvationAlertRequest,
    escalation_exhausted_note,
    shell_evidence_note,
    starvation_evidence_note,
    surface_escalation_exhausted_alert,
    surface_shell_prolonged_alert,
    surface_starvation_alert,
)
from _supervisor_attention_observe import (
    LivenessAttention,
    ObserveRequest,
    observe_liveness_attention,
)
from _supervisor_consensus_overdue import (
    CONSENSUS_OVERDUE_STATUS,
    ConsensusOverdueRequest,
    consensus_overdue_decision,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CONSENSUS_OVERDUE_STATUS",
    "AttentionDecision",
    "AttentionRequest",
    "ConsensusOverdueRequest",
    "EscalationExhaustedAlertRequest",
    "LivenessAttention",
    "ObserveRequest",
    "ShellAlertRequest",
    "StarvationAlertRequest",
    "blocked_starvation_decision",
    "consensus_overdue_decision",
    "escalation_exhausted_note",
    "observe_liveness_attention",
    "pre_busy_attention_decision",
    "shell_evidence_note",
    "starvation_evidence_note",
    "surface_escalation_exhausted_alert",
    "surface_shell_prolonged_alert",
    "surface_starvation_alert",
]


@dataclass(frozen=True, kw_only=True)
class AttentionDecision:
    status: str
    note: str
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class AttentionRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    attention: LivenessAttention
    idle: bool
    gate: bool
    blocked: str | None
    blocked_age: float | None
    act: bool


def _starvation_request(*, request: AttentionRequest) -> StarvationAlertRequest:
    return StarvationAlertRequest(
        sup=request.sup,
        track=request.track,
        session=request.session,
        pane=request.pane,
        age=request.attention.starvation_age or 0.0,
        blocked=request.blocked,
        blocked_age=request.blocked_age,
        gate=request.gate,
        shell_age=request.attention.shell_age if request.attention.shell_only else None,
    )


def _starvation_conditions(*, request: StarvationAlertRequest, act: bool) -> set[str]:
    if act:
        return surface_starvation_alert(request=request)
    return {"winddown-starved"}


def _escalation_exhausted_request(*, request: AttentionRequest) -> EscalationExhaustedAlertRequest:
    return EscalationExhaustedAlertRequest(
        sup=request.sup,
        track=request.track,
        session=request.session,
        pane=request.pane,
        age=request.attention.escalation_exhausted_age or 0.0,
    )


def _escalation_exhausted_conditions(
    *, request: EscalationExhaustedAlertRequest, act: bool
) -> set[str]:
    if act:
        return surface_escalation_exhausted_alert(request=request)
    return {"escalation-exhausted"}


def pre_busy_attention_decision(*, request: AttentionRequest) -> AttentionDecision | None:
    attention = request.attention
    if attention.supervisor_state_stale:
        freshness = _supervisor_supervisor_state.SupervisorStateFreshness(
            stale=True,
            age=attention.supervisor_state_age,
            reason=attention.supervisor_state_reason,
        )
        active = (
            _supervisor_supervisor_state.surface_supervisor_state_stale_alert(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.pane,
                freshness=freshness,
            )
            if request.act
            else {_supervisor_supervisor_state.SUPERVISOR_STATE_STALE_STATUS}
        )
        return AttentionDecision(
            status=_supervisor_supervisor_state.SUPERVISOR_STATE_STALE_STATUS,
            note=_supervisor_supervisor_state.supervisor_state_stale_note(freshness=freshness),
            active_conditions=active,
        )
    if attention.escalation_exhausted_due:
        exhausted = _escalation_exhausted_request(request=request)
        return AttentionDecision(
            status="escalation-exhausted",
            note=escalation_exhausted_note(request=exhausted),
            active_conditions=_escalation_exhausted_conditions(request=exhausted, act=request.act),
        )
    if (
        attention.starved_due
        and not attention.generating
        and (not request.idle or attention.shell_only)
        and not (request.gate or request.blocked is not None)
    ):
        starvation = _starvation_request(request=request)
        return AttentionDecision(
            status="winddown-starved",
            note=starvation_evidence_note(request=starvation),
            active_conditions=_starvation_conditions(request=starvation, act=request.act),
        )
    if attention.shell_due and attention.shell_only and not attention.starving_now:
        shell = ShellAlertRequest(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.pane,
            age=attention.shell_age or 0.0,
        )
        active = (
            surface_shell_prolonged_alert(request=shell) if request.act else {"shell-prolonged"}
        )
        return AttentionDecision(
            status="shell-prolonged",
            note=shell_evidence_note(age=attention.shell_age),
            active_conditions=active,
        )
    return None


def blocked_starvation_decision(*, request: AttentionRequest) -> AttentionDecision | None:
    attention = request.attention
    if not (attention.starved_due and not attention.generating):
        return None
    starvation = _starvation_request(request=request)
    return AttentionDecision(
        status="blocked:human",
        note=starvation_evidence_note(request=starvation),
        active_conditions=_starvation_conditions(request=starvation, act=request.act),
    )
