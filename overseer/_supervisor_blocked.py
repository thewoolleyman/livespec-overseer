"""Blocked-human branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_liveness
import _supervisor_nudge
import _supervisor_state
import registry
import signals
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["BlockedDecision", "BlockedRequest", "blocked_human"]


@dataclass(frozen=True, kw_only=True)
class BlockedDecision:
    note: str | None
    ready: bool
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class BlockedRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    ready: bool
    blocked: str | None
    blocked_age: float | None
    blocked_age_label: str | None
    declared: signals.TrackState | None
    istate: InjectState
    note: str | None
    shell_only: bool
    attention: _supervisor_attention.LivenessAttention
    gate: bool
    act: bool


def blocked_human(*, request: BlockedRequest) -> BlockedDecision:
    active_conditions: set[str] = set()
    note = request.note
    ready = request.ready
    if request.shell_only:
        note = _supervisor_liveness.append_note(
            note=note, extra=_supervisor_attention.shell_evidence_note()
        )
    attention_request = _supervisor_attention.AttentionRequest(
        sup=request.sup,
        track=request.track,
        session=request.session,
        pane=request.pane,
        attention=request.attention,
        idle=False,
        gate=request.gate,
        blocked=request.blocked,
        blocked_age=request.blocked_age,
        act=request.act,
    )
    blocked_attention = _supervisor_attention.blocked_starvation_decision(request=attention_request)
    if blocked_attention is not None:
        note = _supervisor_liveness.append_note(note=note, extra=blocked_attention.note)

    if request.act:
        # A structured gate (like a background shell) is not evidence that a
        # session resumed work after declaring ready.  Keep the declaration for
        # the next genuinely idle, settled tick instead of consuming it here.
        ready = _supervisor_state.void_if_stale(
            sup=request.sup, track=request.track, ready=ready, resumed_work=False
        )
        # A gate / block is also "non-idle" — drop a stale nudge marker (safe: the
        # helper re-reads and leaves a session-written `blocked` untouched).
        _supervisor_nudge.clear_idle_nudge_state(sup=request.sup, track=request.track)
        detail = request.blocked if request.blocked else "structured gate on pane"
        if blocked_attention is not None:
            active_conditions.update(blocked_attention.active_conditions)
        # The decision belongs to the TRACKED session, which is already showing
        # it in its own pane. The overseer NOTIFIES and hands over coordinates;
        # it never re-asks the question itself (invariant 8).
        active_conditions.update(
            _supervisor_liveness.surface_blocked_alerts(
                request=_supervisor_liveness.BlockedAlertRequest(
                    sup=request.sup,
                    track=request.track,
                    session=request.session,
                    pane=request.pane,
                    detail=detail,
                    declaration_mtime=request.declared.mtime
                    if request.blocked is not None and request.declared
                    else None,
                    blocked_age=request.blocked_age if request.blocked is not None else None,
                    blocked_age_label=request.blocked_age_label
                    if request.blocked is not None
                    else None,
                    istate=request.istate,
                )
            )
        )
    else:
        active_conditions.add("blocked-human")
    return BlockedDecision(note=note, ready=ready, active_conditions=active_conditions)
