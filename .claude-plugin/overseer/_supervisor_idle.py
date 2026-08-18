"""Idle-above-threshold branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_nudge
import _supervisor_offer
import registry
import signals
from _supervisor_config import IDLE_NUDGE_AFTER, track_key
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
    foreman_was_escalated = (
        *track_key(repo=request.track.repo, topic=request.track.topic),
        "foreman-escalated",
    ) in request.sup.alerted
    if not foreman_was_escalated and not signals.topic_reserved_for_supervisor(topic=request.topic):
        _supervisor_offer.surface_supervision_offer(
            sup=request.sup, track=request.track, act=request.act
        )
    # Idle at an empty prompt with the context ABOVE the wind-down threshold. If
    # the session has declared nothing, nudge it ONCE this episode to keep going
    # rather than stop early (the inverse of the wrap-up). The daemon-written
    # `idle-with-context-left` marker makes it single-prompt; it clears when the
    # session next goes non-idle, re-arming a fresh nudge for the next episode.
    nudged_already = (
        request.declared is not None
        and request.declared.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT
    )
    daemon_diagnostic = (
        request.declared is not None
        and signals.valid_token(token=request.declared.token)
        and not signals.valid_session_token(token=request.declared.token)
    )
    has_context_left = request.eff_ctx is not None and request.eff_ctx > request.threshold
    # Claude's own `waiting` = at a gate/prompt for the human. Even when no
    # structured gate is visible in the capture (it scrolled, or it is a prose
    # question a YOLO session cannot raise as a prompt), that IS "a blocking
    # question for the human" — so it must NOT be nudged to keep going.
    waiting_on_human = request.claude_status == "waiting"
    # `eff_ctx is not None` is spelled out here as well as inside
    # `has_context_left` so the type checker can narrow it for the
    # `_nudge_idle_with_context` call below. It is not redundant to a reader
    # either: a nudge needs a KNOWN remaining-context percentage to quote.
    if not (
        request.eff_ctx is not None
        and has_context_left
        and not waiting_on_human
        and (request.declared is None or nudged_already or daemon_diagnostic)
    ):
        return "idle"
    idle_long_enough = (
        request.istate.idle_since is not None
        and (request.sup.now() - request.istate.idle_since) >= IDLE_NUDGE_AFTER
    )
    # Fire the nudge ONLY after the session has been continuously idle for at
    # least `IDLE_NUDGE_AFTER` (maintainer 2026-07-18: the nudge was "too
    # aggressive, TOO SOON", interrupting sessions merely between turns). The
    # status still reads `idle-with-context-left` immediately (it is descriptive,
    # not an attention row); only the keystroke waits for the 1-hour floor.
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
