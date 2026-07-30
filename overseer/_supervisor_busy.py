"""Busy branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_liveness
import _supervisor_nudge
import _supervisor_state
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["BusyDecision", "BusyRequest", "busy"]


@dataclass(frozen=True, kw_only=True)
class BusyDecision:
    note: str | None
    ready: bool
    blocked: str | None
    blocked_age: float | None
    blocked_age_label: str | None


@dataclass(frozen=True, kw_only=True)
class BusyRequest:
    sup: Supervisor
    track: registry.Track
    capture: str
    claude_status: str | None
    codex_fallback: bool
    generating: bool
    malformed: bool
    note: str | None
    ready: bool
    blocked: str | None
    act: bool


def busy(*, request: BusyRequest) -> BusyDecision:
    note = request.note
    ready = request.ready
    blocked = request.blocked
    blocked_age: float | None = None
    blocked_age_label: str | None = None
    if request.act:
        blocked = _supervisor_state.void_stale_blocked(
            sup=request.sup,
            track=request.track,
            blocked=blocked,
            generating=request.generating,
        )
        declared = signals.read_state(repo=request.track.repo, topic=request.track.topic)
        blocked_age = _supervisor_liveness.blocked_age(sup=request.sup, declared=declared)
        blocked_age_label = _supervisor_liveness.age_label_or_none(seconds=blocked_age)
        if not request.malformed:
            note = _supervisor_liveness.blocked_note(
                blocked=blocked, blocked_age_label=blocked_age_label
            )
    if not signals.is_busy(capture_text=request.capture):
        if request.claude_status == "shell" or request.codex_fallback:
            note = _supervisor_liveness.append_note(
                note=note if request.malformed else None,
                extra=_supervisor_attention.shell_evidence_note(),
            )
        elif request.claude_status == "busy":  # pragma: no branch
            note = _supervisor_liveness.append_note(
                note=note if request.malformed else None,
                extra="sub-agent (Claude busy)",
            )
    if request.act:
        ready = _supervisor_state.void_if_stale(sup=request.sup, track=request.track, ready=ready)
        _supervisor_nudge.clear_idle_nudge_state(sup=request.sup, track=request.track)
    return BusyDecision(
        note=note,
        ready=ready,
        blocked=blocked,
        blocked_age=blocked_age,
        blocked_age_label=blocked_age_label,
    )
