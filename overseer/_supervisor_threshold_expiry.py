"""Ready-expiry notice branch for below-threshold supervision."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_busy_delivery
import _supervisor_launch
import _supervisor_observe
import _supervisor_round_recovery
import registry
import signals
from _supervisor_config import track_key
from _supervisor_prompts import expiry_notice_message
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_threshold import ThresholdRequest

__all__: list[str] = [
    "busy_evidence_blocker",
    "close_round_if_no_longer_current",
    "fresh_guarded_paste_observation",
    "maybe_send_expiry_notice",
]


_KNOWN_CLAUDE_STATUSES = frozenset({"busy", "idle", "shell", "waiting"})


def busy_evidence_blocker(*, obs: Observation) -> str | None:
    """Name the concrete busy evidence that is blocking ready-certification, or None.

    Since spec v058 the guarded paste also lands in a BUSY pane whose input is
    positively empty, so any busy class can be live when a wrap-up or an expiry notice
    lands: a background shell (Claude registry ``shell``, or the Codex descendant-shell
    fallback), or a running turn / in-process sub-agent (Claude ``busy`` or a generating
    spinner). Each is evidence that keeps a ``ready`` from certifying under the
    restart interlock's no-busy gate, so the message names it and the session stops it
    first. This reads only observed facts and decides nothing: it does not authorize a
    restart and does not weaken the cardinal rule.
    """
    if obs.claude_status == "shell" or obs.codex_fallback:
        return "a background shell is still running under this pane"
    if obs.claude_status == "busy" or signals.is_busy(capture_text=obs.capture):
        # Spec v058 delivers into a busy pane whose input is empty; the session must stop
        # its own turn, sub-agents and monitors before a `ready` can certify.
        return "this session is still working (a running turn, sub-agents or monitors)"
    return None


def _declaration_signature(*, obs: Observation) -> tuple[str, str, float] | None:
    if obs.declared is None:
        return None
    return (obs.declared.token, obs.declared.detail, obs.declared.mtime)


def _claude_status_unavailable(*, fresh: Observation) -> bool:
    return not fresh.is_codex and fresh.claude_status is None


def _input_authorization_changed(*, settled: Observation, fresh: Observation) -> bool:
    """The busy-delivery recheck: only INPUT-protecting inputs may cancel the paste.

    Spec v058 (contracts.md, the wrap-up injection): identity, declaration, gate,
    human-wait and eligible-input state are re-read; a change in busy evidence alone —
    the capture, the generating spinner, the registry's busy/shell status — MUST NOT
    cancel it, or a session that never stops working could never be wound down.
    """
    return (
        fresh.is_codex != settled.is_codex
        or _supervisor_busy_delivery.obs_input_empty(obs=fresh)
        != _supervisor_busy_delivery.obs_input_empty(obs=settled)
        or fresh.gate != settled.gate
        or (fresh.claude_status == "waiting") != (settled.claude_status == "waiting")
        or fresh.ready != settled.ready
        or fresh.malformed != settled.malformed
        or fresh.blocked != settled.blocked
        or fresh.acked != settled.acked
        or _declaration_signature(obs=fresh) != _declaration_signature(obs=settled)
    )


def _authorization_inputs_changed(*, request: ThresholdRequest, fresh: Observation) -> bool:
    settled = request.obs
    if settled.busy:
        return _input_authorization_changed(settled=settled, fresh=fresh)
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


def fresh_guarded_paste_observation(
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
    if _claude_status_unavailable(fresh=fresh) or (
        fresh.claude_status is not None and fresh.claude_status not in _KNOWN_CLAUDE_STATUSES
    ):
        return None
    if _authorization_inputs_changed(request=request, fresh=fresh):
        return None
    if request.obs.busy:
        return _busy_delivery_guarded(
            request=request, fresh=fresh, require_below_threshold=require_below_threshold
        )
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
        or fresh.acked
    ):
        return None
    return fresh


def _busy_delivery_guarded(
    *, request: ThresholdRequest, fresh: Observation, require_below_threshold: bool
) -> Observation | None:
    """The input-only paste predicate for a busy pane (spec v058)."""
    if (
        fresh.eff_ctx is None
        or (require_below_threshold and fresh.eff_ctx > request.threshold)
        or not _supervisor_busy_delivery.obs_input_empty(obs=fresh)
        or fresh.gate
        or fresh.claude_status == "waiting"
        or (
            fresh.declared is not None
            and fresh.declared.token in (signals.STATE_BLOCKED, signals.STATE_READY)
        )
        or fresh.acked
    ):
        return None
    return fresh


def _fresh_expiry_notice_observation(*, request: ThresholdRequest) -> Observation | None:
    """Re-read every expiry-notice paste authorization input immediately before acting."""
    fresh = fresh_guarded_paste_observation(request=request, require_below_threshold=False)
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


def close_round_if_no_longer_current(*, request: ThresholdRequest) -> None:
    if not request.act:
        return
    _ = _supervisor_round_recovery.close_recovered_round(
        request=_supervisor_round_recovery.RecoveryRequest(
            sup=request.sup,
            track=request.track,
            obs=request.obs,
            session=request.session,
            target=request.target,
            threshold=request.threshold,
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
    close_round_if_no_longer_current(request=request)
    if not _expiry_notice_due_for_track(request=request, obs=request.obs):
        return False
    fresh = _fresh_expiry_notice_observation(request=request)
    if fresh is None:
        return False
    message = expiry_notice_message(
        repo=request.track.repo,
        topic=request.track.topic,
        blocker=busy_evidence_blocker(obs=fresh),
    )
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
