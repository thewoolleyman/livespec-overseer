"""Below-threshold wrap-up branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_nudge
import _supervisor_observe
import _supervisor_restart
import registry
import signals
from _supervisor_config import DANGER_CTX_REMAINING, track_key
from _supervisor_prompts import expiry_notice_message
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "ThresholdDecision",
    "ThresholdRequest",
    "maybe_send_expiry_notice",
    "threshold",
]


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


def _claude_status_unavailable(*, fresh: Observation) -> bool:
    return not fresh.is_codex and fresh.claude_status is None


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


def _fresh_guarded_paste_observation(
    *, request: ThresholdRequest, require_below_threshold: bool
) -> Observation | None:
    """Re-read every paste authorization input immediately before acting."""
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
    if _claude_status_unavailable(fresh=fresh):
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
    ready = fresh.declared is not None and fresh.declared.token == signals.STATE_READY
    if (
        fresh.eff_ctx is None
        or (require_below_threshold and fresh.eff_ctx > request.threshold)
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


def _fresh_threshold_observation(*, request: ThresholdRequest) -> Observation | None:
    """Re-read every paste authorization input immediately before opening a round."""
    return _fresh_guarded_paste_observation(request=request, require_below_threshold=True)


def _fresh_expiry_notice_observation(*, request: ThresholdRequest) -> Observation | None:
    """Re-read every expiry-notice paste authorization input immediately before acting."""
    fresh = _fresh_guarded_paste_observation(request=request, require_below_threshold=False)
    if fresh is None or not _expiry_notice_due_for_track(request=request, obs=fresh):
        return None
    return fresh


def _expiry_notice_due_for_track(*, request: ThresholdRequest, obs: Observation) -> bool:
    record = obs.round_record
    return (
        record.at is not None
        and record.expired_at is not None
        and record.malformed_reason is None
        and not record.expiry_notice_sent
        and obs.eff_ctx is not None
        and not registry.read_resume_pending(
            repo=request.track.repo,
            topic=request.track.topic,
            stamp_path=request.sup.stamp_path,
        )
    )


def maybe_send_expiry_notice(*, request: ThresholdRequest) -> bool:
    """Send the round's single expiry-notice if its guarded predicate passes.

    The trigger is the recorded expiry, not the below-threshold context trigger, so
    the notice may fire at any known context while its round remains open. The
    once-per-round bound is DURABLE — it is marked in the round's sidecar beside the
    notified bands — so a daemon restart never re-sends a notice already sent, and a
    failed paste simply leaves the notice due on a later observation.
    """
    if not _expiry_notice_due_for_track(request=request, obs=request.obs):
        return False
    fresh = _fresh_expiry_notice_observation(request=request)
    if fresh is None:
        return False
    message = expiry_notice_message(repo=request.track.repo, topic=request.track.topic)
    sent = _supervisor_launch.submit_prompt(
        sup=request.sup,
        target=request.target,
        text=message,
        expect_codex=fresh.is_codex,
    )
    if sent:
        _ = registry.mark_expiry_notice_sent(
            repo=request.track.repo,
            topic=request.track.topic,
            stamp_path=request.sup.stamp_path,
        )
        request.sup.log(
            message=f"injected ready-expiry notice into {request.track.repo}::{request.track.topic}"
        )
        return True
    return False


def threshold(*, request: ThresholdRequest) -> ThresholdDecision:
    active_conditions: set[str] = set()
    obs = request.obs
    eff_ctx = obs.eff_ctx if obs.eff_ctx is not None else request.threshold
    # A FRESH `winding-down` ACK buys patience: the session heard us and is
    # wrapping up, so stop re-warning (never keystroke into a session that is
    # actively winding down). A STALE ACK resumes escalating — an ACK must not
    # become an infinite stall — but still never authorizes an act.
    raw_ready = obs.declared is not None and obs.declared.token == signals.STATE_READY
    if request.act and not obs.acked and not obs.malformed and not raw_ready:
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
        # A standing ready has its own certification surface.  Calling it a
        # non-responder here is false (and conceals the real interlock reason).
        if request.act and not raw_ready:
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
