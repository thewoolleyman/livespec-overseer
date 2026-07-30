"""Idle-above-threshold branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_nudge
import _supervisor_offer
import registry
import signals
from _supervisor_config import IDLE_NUDGE_AFTER
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["IdleRequest", "idle_room"]


@dataclass(frozen=True, kw_only=True)
class IdleRequest:
    sup: Supervisor
    track: registry.Track
    target: str
    topic: str
    eff_ctx: int | None
    threshold: int
    declared: signals.TrackState | None
    claude_status: str | None
    istate: InjectState
    act: bool
    is_codex: bool


def idle_room(*, request: IdleRequest) -> str:
    if not signals.topic_reserved_for_supervisor(topic=request.topic):
        _supervisor_offer.surface_supervision_offer(
            sup=request.sup, track=request.track, act=request.act
        )
    nudged_already = (
        request.declared is not None
        and request.declared.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT
    )
    has_context_left = request.eff_ctx is not None and request.eff_ctx > request.threshold
    waiting_on_human = request.claude_status == "waiting"
    if not (
        request.eff_ctx is not None
        and has_context_left
        and not waiting_on_human
        and (request.declared is None or nudged_already)
    ):
        return "idle"
    idle_long_enough = (
        request.istate.idle_since is not None
        and (request.sup.now() - request.istate.idle_since) >= IDLE_NUDGE_AFTER
    )
    if request.act and not nudged_already and idle_long_enough:
        _supervisor_nudge.nudge_idle_with_context(
            sup=request.sup,
            track=request.track,
            target=request.target,
            eff_ctx=request.eff_ctx,
            threshold=request.threshold,
            is_codex=request.is_codex,
        )
    return "idle-with-context-left"
