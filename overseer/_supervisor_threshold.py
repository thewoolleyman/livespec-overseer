"""Below-threshold wrap-up branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_nudge
import _supervisor_observe
import _supervisor_restart
import registry
import signals
from _supervisor_config import DANGER_CTX_REMAINING, track_key
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["ThresholdDecision", "ThresholdRequest", "threshold"]


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


_KNOWN_CLAUDE_STATUSES = frozenset({"busy", "idle", "shell", "waiting"})


def _declaration_signature(*, obs: Observation) -> tuple[str, str, float] | None:
    if obs.declared is None:
        return None
    return (obs.declared.token, obs.declared.detail, obs.declared.mtime)


def _adopted_claude_status_missing(*, request: ThresholdRequest, fresh: Observation) -> bool:
    return (
        not fresh.is_codex
        and fresh.claude_status is None
        and request.session in request.sup.claude_names_by_session
    )


def _authorization_inputs_changed(*, request: ThresholdRequest, fresh: Observation) -> bool:
    settled = request.obs
    return (
        fresh.capture != settled.capture
        or fresh.is_codex != settled.is_codex
        or fresh.busy != settled.busy
        or fresh.gate != settled.gate
        or fresh.idle != settled.idle
        or fresh.codex_fallback != settled.codex_fallback
        or fresh.claude_status != settled.claude_status
        or fresh.ready != settled.ready
        or fresh.malformed != settled.malformed
        or fresh.blocked != settled.blocked
        or fresh.acked != settled.acked
        or _declaration_signature(obs=fresh) != _declaration_signature(obs=settled)
    )


def _fresh_threshold_observation(*, request: ThresholdRequest) -> Observation | None:
    """Re-read every paste authorization input immediately before opening a round."""
    if not _supervisor_observe.pane_is_managed(
        sup=request.sup,
        target=request.target,
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
    ):
        return None
    fresh = _supervisor_observe.observe(
        sup=request.sup,
        track=request.track,
        session=request.session,
        target=request.target,
        key=track_key(repo=request.track.repo, topic=request.track.topic),
    )
    if _adopted_claude_status_missing(request=request, fresh=fresh):
        return None
    if fresh.claude_status is not None and fresh.claude_status not in _KNOWN_CLAUDE_STATUSES:
        return None
    if _authorization_inputs_changed(request=request, fresh=fresh):
        return None
    generating = signals.is_busy(capture_text=fresh.capture) or fresh.claude_status == "busy"
    shell_only = (not signals.is_busy(capture_text=fresh.capture)) and (
        fresh.claude_status == "shell" or fresh.codex_fallback
    )
    blocked = fresh.declared is not None and fresh.declared.token == signals.STATE_BLOCKED
    ready = fresh.ready or (
        shell_only and fresh.declared is not None and fresh.declared.token == signals.STATE_READY
    )
    if (
        fresh.eff_ctx is None
        or fresh.eff_ctx > request.threshold
        or not fresh.idle
        or fresh.gate
        or generating
        or (fresh.busy and not shell_only)
        or fresh.claude_status == "waiting"
        or blocked
        or ready
        or fresh.malformed
        or fresh.acked
    ):
        return None
    return fresh


def threshold(*, request: ThresholdRequest) -> ThresholdDecision:
    active_conditions: set[str] = set()
    obs = request.obs
    eff_ctx = obs.eff_ctx if obs.eff_ctx is not None else request.threshold
    # A FRESH `winding-down` ACK buys patience: the session heard us and is
    # wrapping up, so stop re-warning (never keystroke into a session that is
    # actively winding down). A STALE ACK resumes escalating — an ACK must not
    # become an infinite stall — but still never authorizes an act.
    if request.act and not obs.acked and not obs.malformed:
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
        active_conditions.add("default")
        if request.act:
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
