"""Pre-idle active branch group for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_blocked
import _supervisor_busy
import _supervisor_foreman_escalation
import _supervisor_liveness
import foreman_pane_claim
import registry
import signals
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_evaluate_attention import EvaluationAttention

__all__: list[str] = ["ActiveDecision", "ActiveRequest", "active_decision"]


@dataclass(frozen=True, kw_only=True)
class ActiveDecision:
    status: str
    note: str | None
    ready: bool
    blocked: str | None
    blocked_age: float | None
    blocked_age_label: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class ActiveRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    target: str
    attention: EvaluationAttention
    capture: str
    busy: bool
    gate: bool
    idle: bool
    codex_fallback: bool
    claude_status: str | None
    eff_ctx: int | None
    istate: InjectState
    threshold: int
    declared: signals.TrackState | None
    malformed: bool
    blocked: str | None
    ready: bool
    blocked_age: float | None
    blocked_age_label: str | None
    note: str | None
    act: bool


def _ready_declared(*, request: ActiveRequest) -> bool:
    return request.declared is not None and request.declared.token == signals.STATE_READY


def active_decision(*, request: ActiveRequest) -> ActiveDecision | None:
    active_conditions: set[str] = set()
    attention_request = _supervisor_attention.AttentionRequest(
        sup=request.sup,
        track=request.track,
        session=request.session,
        pane=request.target,
        attention=request.attention.attention,
        idle=request.idle,
        gate=request.gate,
        blocked=request.blocked,
        blocked_age=request.blocked_age,
        act=request.act,
    )
    attention_decision = _supervisor_attention.pre_busy_attention_decision(
        request=attention_request
    )
    if attention_decision is not None:
        active_conditions.update(attention_decision.active_conditions)
        return ActiveDecision(
            status=attention_decision.status,
            note=attention_decision.note,
            ready=request.ready,
            blocked=request.blocked,
            blocked_age=request.blocked_age,
            blocked_age_label=request.blocked_age_label,
            active_conditions=active_conditions,
        )
    if (
        foreman_escalation := _supervisor_foreman_escalation.attention_decision(
            sup=request.sup,
            track=request.track,
            session=request.session,
            pane=request.target,
            act=request.act,
        )
    ) is not None:
        active_conditions.update(foreman_escalation.active_conditions)
        return ActiveDecision(
            status=foreman_escalation.status,
            note=foreman_escalation.note,
            ready=request.ready,
            blocked=request.blocked,
            blocked_age=request.blocked_age,
            blocked_age_label=request.blocked_age_label,
            active_conditions=active_conditions,
        )
    if (
        foreman_claim := foreman_pane_claim.active_pane_claim(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.target,
            now=request.sup.now(),
        )
    ) is not None:
        note = _supervisor_liveness.append_note(
            note=request.note,
            extra=(
                "foreman owns this pane"
                f" ({foreman_claim.runtime}, {foreman_claim.question_fingerprint})"
            ),
        )
        return ActiveDecision(
            status="blocked:human",
            note=note,
            ready=request.ready,
            blocked=request.blocked,
            blocked_age=request.blocked_age,
            blocked_age_label=request.blocked_age_label,
            active_conditions={"blocked-human"},
        )
    shell_only = request.attention.shell_only
    generating = request.attention.generating
    if (
        request.busy
        and (
            request.ready
            or not (
                shell_only and request.eff_ctx is not None and request.eff_ctx <= request.threshold
            )
        )
        and not ((request.gate or request.blocked is not None) and not generating)
    ):
        busy_decision = _supervisor_busy.busy(
            request=_supervisor_busy.BusyRequest(
                sup=request.sup,
                track=request.track,
                capture=request.capture,
                claude_status=request.claude_status,
                codex_fallback=request.codex_fallback,
                generating=generating,
                malformed=request.malformed,
                note=request.note,
                ready=_ready_declared(request=request),
                blocked=request.blocked,
                act=request.act,
            )
        )
        return ActiveDecision(
            status="working",
            note=busy_decision.note,
            ready=busy_decision.ready,
            blocked=busy_decision.blocked,
            blocked_age=busy_decision.blocked_age,
            blocked_age_label=busy_decision.blocked_age_label,
            active_conditions=active_conditions,
        )
    if request.gate or request.blocked is not None:
        blocked_decision = _supervisor_blocked.blocked_human(
            request=_supervisor_blocked.BlockedRequest(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.target,
                ready=_ready_declared(request=request),
                blocked=request.blocked,
                blocked_age=request.blocked_age,
                blocked_age_label=request.blocked_age_label,
                declared=request.declared,
                istate=request.istate,
                note=request.note,
                shell_only=shell_only,
                attention=request.attention.attention,
                gate=request.gate,
                act=request.act,
            )
        )
        return ActiveDecision(
            status="blocked:human",
            note=blocked_decision.note,
            ready=blocked_decision.ready,
            blocked=request.blocked,
            blocked_age=request.blocked_age,
            blocked_age_label=request.blocked_age_label,
            active_conditions=blocked_decision.active_conditions,
        )
    return None
