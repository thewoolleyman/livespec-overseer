"""Pre-idle active branch group for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_blocked
import _supervisor_busy
import _supervisor_busy_delivery
import _supervisor_onboarding
import registry
import signals
from _supervisor_active_models import ActiveDecision
from _supervisor_records import InjectState, Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_evaluate_attention import EvaluationAttention

__all__: list[str] = ["ActiveDecision", "ActiveRequest", "active_decision"]


@dataclass(frozen=True, kw_only=True)
class ActiveRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    target: str
    attention: EvaluationAttention
    obs: Observation
    capture: str
    busy: bool
    gate: bool
    idle: bool
    ctx_changed: bool
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


def _done_declared(*, request: ActiveRequest) -> bool:
    return request.declared is not None and request.declared.token == signals.STATE_DONE


def active_decision(*, request: ActiveRequest) -> ActiveDecision | None:
    active_conditions: set[str] = set()
    # The terminal declaration has no expiry and no evidence-based void (SPECIFICATION
    # v061): neither observed generation, nor background activity, nor idleness, nor age
    # retires it. A session handed new work clears its own `done` first, which is the
    # only thing that ends it short of its plan being un-archived.
    if _done_declared(request=request) and not request.gate:
        return ActiveDecision(
            status=signals.STATE_DONE,
            note=request.declared.detail if request.declared is not None else None,
            ready=False,
            blocked=None,
            blocked_age=None,
            blocked_age_label=None,
            active_conditions=active_conditions,
        )
    onboarding = _supervisor_onboarding.active_decision(request=request)
    if onboarding is not None:
        return onboarding
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
    shell_only = request.attention.shell_only
    generating = request.attention.generating
    if (
        (
            request.busy
            or (
                request.ctx_changed
                and request.gate
                and request.istate.blocked_human_stall_since is None
            )
        )
        and (
            request.ready
            or not (
                (
                    shell_only
                    and request.eff_ctx is not None
                    and request.eff_ctx <= request.threshold
                )
                # Spec v058: a busy pane whose input is positively empty still receives
                # the owed wind-down; only input-protecting evidence holds it back.
                or _supervisor_busy_delivery.deliverable_while_busy(
                    obs=request.obs, threshold=request.threshold
                )
            )
        )
        and not (
            (request.gate or request.blocked is not None)
            and not (generating or request.ctx_changed)
        )
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
        note = busy_decision.note
        if _supervisor_busy_delivery.codex_busy_withheld(
            obs=request.obs, threshold=request.threshold
        ):
            note = _supervisor_busy_delivery.surface_codex_withheld(
                sup=request.sup,
                track=request.track,
                session=request.session,
                pane=request.target,
                note=note,
                act=request.act,
            )
            active_conditions.add(_supervisor_busy_delivery.CODEX_BUSY_WITHHELD_CONDITION)
        return ActiveDecision(
            status="working",
            note=note,
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
        active_conditions.update(blocked_decision.active_conditions)
        return ActiveDecision(
            status="blocked:human",
            note=blocked_decision.note,
            ready=blocked_decision.ready,
            blocked=request.blocked,
            blocked_age=request.blocked_age,
            blocked_age_label=request.blocked_age_label,
            active_conditions=active_conditions,
        )
    return None
