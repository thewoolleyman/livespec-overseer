"""_supervisor_evaluate — phase 2 of a tick: the decision cascade.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module is ONE function, the decision cascade itself; extracted
leg details live in the neighbouring ``_supervisor_*`` branch modules. Everything
:func:`evaluate` decides ON is gathered by :mod:`_supervisor_observe` first, and
everything it decides to DO is carried out by :mod:`_supervisor_restart`,
:mod:`_supervisor_nudge`, :mod:`_supervisor_state` and :mod:`_supervisor_offer` — so
what is left here is purely the ORDER, which is the design.

Read `evaluate`'s own docstring before changing anything in it: its length is the
number of distinct states a track can be in, and a maintainer ruling of 2026-07-19
governs what may and may not be cut out of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_blocked
import _supervisor_busy
import _supervisor_evaluate_attention
import _supervisor_evaluate_idle
import _supervisor_evaluate_notes
import _supervisor_evaluate_target
import _supervisor_liveness
import _supervisor_observe
import _supervisor_picker_stall
import _supervisor_progress
import _supervisor_restart_attention
import foreman_pane_claim
import registry
import signals
from _supervisor_records import Observation
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["evaluate"]


def _record_observed_session_identity(
    *, sup: Supervisor, track: registry.Track, obs: Observation, act: bool
) -> None:
    if not act or obs.session_identity is None:
        return
    _ = registry.record_observed_session_identity(
        repo=track.repo,
        topic=track.topic,
        session_identity=obs.session_identity,
        store_path=sup.store_path,
    )


def evaluate(  # noqa: PLR0915 — see "On the size of this function"
    *, sup: Supervisor, track: registry.Track, act: bool
) -> RowView:
    """Derive a track's status and (when ``act``) perform its side effects.

    ``act=False`` is the read-only path used by the ``list`` command: it
    captures the pane and reads markers but performs NO paste / respawn /
    stamp write. The daemon loop calls with ``act=True``.

    **On the size of this function.** What remains after :meth:`_observe` was
    split out is the DECISION CASCADE: an ordered sequence of guards, each of
    which either returns a row or falls through to the next. Its length is the
    number of distinct states a track can be in, and its ordering IS the
    design — the cardinal rule (never restart a session that has not declared
    itself ready) is enforced by which guard comes first, not by any single
    guard in isolation.

    Extracting the fact-gathering was a real seam and is done. Later extractions
    kept the same constraint: this function still owns the readable precedence
    ORDER, while branch modules own the side-effect detail for individual legs.
    The test for any extraction is whether the cascade still reads top-to-bottom
    in one pass here, not whether a helper exists elsewhere.

    **The authorised branch helpers, and their exact bounds.** The self-healing
    resume retry, attention pre-check, busy, blocked-human, stale-context,
    below-threshold, and idle-above-threshold details live in neighbouring
    helpers. Each call sits at the exact position its block occupied, so the
    cascade order remains visible here. What moved is each leg's DETAIL, not its
    place in the order; load-bearing rationale that explains a branch remains
    beside that branch's code.
    """
    resolved = _supervisor_evaluate_target.resolve_evaluate_target(sup=sup, track=track)
    if isinstance(resolved, RowView):
        return resolved
    repo, topic = resolved.repo, resolved.topic
    session, key, target = resolved.session, resolved.key, resolved.pane

    # Phase 1 — OBSERVE. Every fact the guard cascade below decides on is
    # gathered in one place, so the cascade reads as a single top-to-bottom
    # precedence order. Unpacked into locals so each guard reads the same way
    # it always has.
    obs = _supervisor_observe.observe(sup=sup, track=track, session=session, target=target, key=key)
    _record_observed_session_identity(sup=sup, track=track, obs=obs, act=act)
    capture, busy, gate, idle = obs.capture, obs.busy, obs.gate, obs.idle
    codex_fallback = obs.codex_fallback
    claude_status, eff_ctx, istate = obs.claude_status, obs.eff_ctx, obs.istate
    ctx_stale_age = obs.ctx_stale_age
    declared, malformed, blocked, ready = (
        obs.declared,
        obs.malformed,
        obs.blocked,
        obs.ready,
    )

    # Phase 2 — DECIDE.
    settled_streaming_progress = False

    # R1 — self-healing resume retry. The cascade's FIRST leg, and it stays first:
    # it must intercept before the busy/idle cascade below, because a box holding the
    # un-submitted resume text reads as "not idle" and would otherwise fall to
    # `settling` and never retry. Its detail lives in `_supervisor_resume_retry`; the
    # call sits at the leg's exact position so the precedence order still reads
    # top-to-bottom here in one pass.
    post_respawn = _supervisor_restart_attention.post_respawn_decision(
        sup=sup,
        track=track,
        obs=obs,
        act=act,
        session=session,
        target=target,
    )
    if post_respawn is not None:
        return post_respawn

    attention_prepared = _supervisor_evaluate_attention.prepare_evaluation_attention(
        sup=sup, track=track, obs=obs
    )
    threshold = attention_prepared.threshold
    attention = attention_prepared.attention
    generating = attention_prepared.generating
    shell_only = attention_prepared.shell_only

    notes = _supervisor_evaluate_notes.prepare_evaluation_notes(
        request=_supervisor_evaluate_notes.PrepareNotesRequest(
            sup=sup,
            track=track,
            session=session,
            pane=target,
            declared=declared,
            malformed=malformed,
            blocked=blocked,
            ctx_stale_age=ctx_stale_age,
            act=act,
        )
    )
    blocked_age = notes.blocked_age
    blocked_age_label = notes.blocked_age_label
    note, ctx_stale_note = notes.note, notes.ctx_stale_note
    active_conditions = notes.active_conditions

    uncertifiable_ready = _supervisor_liveness.uncertifiable_ready_surface(
        sup=sup, track=track, session=session, pane=target, obs=obs, act=act
    )
    if uncertifiable_ready is not None:
        _ready_note, ready_conditions = uncertifiable_ready
        active_conditions.update(ready_conditions)

    # Precedence, top to bottom. Single-capture `busy` and the human gates
    # are checked first. For an apparently-idle track that would ACT
    # (restart / inject), the daemon first confirms the pane is SETTLED
    # (`_pane_settled`) — a single frame can't see active token-streaming, so
    # a changing pane is treated as `working` and skipped this tick.
    attention_request = _supervisor_attention.AttentionRequest(
        sup=sup,
        track=track,
        session=session,
        pane=target,
        attention=attention,
        idle=idle,
        gate=gate,
        blocked=blocked,
        blocked_age=blocked_age,
        act=act,
    )
    attention_decision = _supervisor_attention.pre_busy_attention_decision(
        request=attention_request
    )
    if attention_decision is not None:
        status = attention_decision.status
        note = attention_decision.note
        active_conditions.update(attention_decision.active_conditions)
    elif (
        foreman_claim := foreman_pane_claim.active_pane_claim(
            repo=repo, topic=topic, session=session, pane=target, now=sup.now()
        )
    ) is not None:
        status = "blocked:human"
        note = _supervisor_liveness.append_note(
            note=note,
            extra=(
                "foreman owns this pane"
                f" ({foreman_claim.runtime}, {foreman_claim.question_fingerprint})"
            ),
        )
        active_conditions.add("blocked-human")
    elif (
        busy
        and (ready or not (shell_only and eff_ctx is not None and eff_ctx <= threshold))
        and not ((gate or blocked is not None) and not generating)
    ):
        status = "working"
        busy_decision = _supervisor_busy.busy(
            request=_supervisor_busy.BusyRequest(
                sup=sup,
                track=track,
                capture=capture,
                claude_status=claude_status,
                codex_fallback=codex_fallback,
                generating=generating,
                malformed=malformed,
                note=note,
                ready=declared is not None and declared.token == signals.STATE_READY,
                blocked=blocked,
                act=act,
            )
        )
        note = busy_decision.note
        ready = busy_decision.ready
        blocked = busy_decision.blocked
        blocked_age = busy_decision.blocked_age
        blocked_age_label = busy_decision.blocked_age_label
    elif gate or blocked is not None:
        status = "blocked:human"
        blocked_decision = _supervisor_blocked.blocked_human(
            request=_supervisor_blocked.BlockedRequest(
                sup=sup,
                track=track,
                session=session,
                pane=target,
                ready=declared is not None and declared.token == signals.STATE_READY,
                blocked=blocked,
                blocked_age=blocked_age,
                blocked_age_label=blocked_age_label,
                declared=declared,
                istate=istate,
                note=note,
                shell_only=shell_only,
                attention=attention,
                gate=gate,
                act=act,
            )
        )
        note = blocked_decision.note
        ready = blocked_decision.ready
        active_conditions.update(blocked_decision.active_conditions)
    else:
        idle_result = _supervisor_evaluate_idle.idle_decision(
            request=_supervisor_evaluate_idle.IdleRequest(
                sup=sup,
                track=track,
                obs=obs,
                session=session,
                target=target,
                threshold=threshold,
                ready=ready,
                uncertifiable_ready=uncertifiable_ready,
                ctx_stale_note=ctx_stale_note,
                note=note,
                act=act,
            )
        )
        status = idle_result.status
        note = idle_result.note
        settled_streaming_progress = idle_result.settled_streaming_progress
        active_conditions.update(idle_result.active_conditions)

    if status != "ctx-stale":
        note = _supervisor_liveness.append_note(note=note, extra=ctx_stale_note)

    picker_stall = _supervisor_picker_stall.apply_picker_stall(
        request=_supervisor_picker_stall.PickerStallRequest(
            sup=sup,
            track=track,
            session=session,
            pane=target,
            status=status,
            note=note,
            obs=obs,
            active_conditions=active_conditions,
            act=act,
        )
    )
    status = picker_stall.status
    note = picker_stall.note
    active_conditions = picker_stall.active_conditions

    view = _supervisor_progress.row_view(
        request=_supervisor_progress.RowViewRequest(
            track=track,
            session=session,
            status=status,
            note=note,
            obs=obs,
            settled_streaming_progress=settled_streaming_progress,
            picker_stall=picker_stall.view,
        )
    )
    # Re-arm edge-triggered alerts per condition, not per row: a track can stay in
    # NEEDS YOU for one reason while a different condition clears and must re-arm.
    if act:
        _supervisor_liveness.clear_alert_conditions(
            sup=sup, repo=repo, topic=topic, conditions=frozenset(active_conditions)
        )
    return view
