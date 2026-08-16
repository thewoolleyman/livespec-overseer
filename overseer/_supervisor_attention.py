"""Report-only liveness attention for shell and wind-down starvation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention_exhausted
import _supervisor_observe
import registry
import signals
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
from _supervisor_config import SHELL_PROLONGED_AFTER, WINDDOWN_STARVED_AFTER
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "AttentionDecision",
    "AttentionRequest",
    "EscalationExhaustedAlertRequest",
    "LivenessAttention",
    "ObserveRequest",
    "ShellAlertRequest",
    "StarvationAlertRequest",
    "blocked_starvation_decision",
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
        escalation_exhausted_age=escalation_exhaustion.age,
        starvation_age=starvation_age,
        shell_age=shell_age,
    )


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
