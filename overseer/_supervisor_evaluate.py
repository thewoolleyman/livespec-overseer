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

import _supervisor_evaluate_active
import _supervisor_evaluate_attention
import _supervisor_evaluate_idle
import _supervisor_evaluate_notes
import _supervisor_evaluate_observation
import _supervisor_evaluate_target
import _supervisor_liveness
import _supervisor_observe
import _supervisor_progress
import _supervisor_restart_attention
import _supervisor_stall_watch
import _supervisor_state
import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["evaluate"]


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
    _supervisor_evaluate_observation.record_observed_session_identity(
        sup=sup, track=track, obs=obs, act=act
    )
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

    # A `ready` declaration that outlived its maximum age EXPIRES here, after the
    # interlock inputs for this tick have already been read. That ordering is the
    # point: `obs` was gathered before this call, so the aged declaration is judged
    # uncertifiable by precondition 3's own age backstop in the SAME observation that
    # expires it — never certifiable in the window before the expiry is recorded.
    _ = _supervisor_state.expire_aged_ready(sup=sup, track=track, act=act)

    # Precedence, top to bottom. Single-capture `busy` and the human gates
    # are checked first. For an apparently-idle track that would ACT
    # (restart / inject), the daemon first confirms the pane is SETTLED
    # (`_pane_settled`) — a single frame can't see active token-streaming, so
    # a changing pane is treated as `working` and skipped this tick.
    active_decision = _supervisor_evaluate_active.active_decision(
        request=_supervisor_evaluate_active.ActiveRequest(
            sup=sup,
            track=track,
            session=session,
            target=target,
            attention=attention_prepared,
            capture=capture,
            busy=busy,
            gate=gate,
            idle=idle,
            codex_fallback=codex_fallback,
            claude_status=claude_status,
            eff_ctx=eff_ctx,
            istate=istate,
            threshold=threshold,
            declared=declared,
            malformed=malformed,
            blocked=blocked,
            ready=ready,
            blocked_age=blocked_age,
            blocked_age_label=blocked_age_label,
            note=note,
            act=act,
        )
    )
    if active_decision is not None:
        status = active_decision.status
        note = active_decision.note
        ready = active_decision.ready
        blocked = active_decision.blocked
        blocked_age = active_decision.blocked_age
        blocked_age_label = active_decision.blocked_age_label
        active_conditions.update(active_decision.active_conditions)
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

    note = _supervisor_evaluate_notes.append_ctx_stale_note(
        status=status, note=note, ctx_stale_note=ctx_stale_note
    )

    monitors = _supervisor_stall_watch.apply_evaluation_monitors(
        request=_supervisor_stall_watch.EvaluationMonitorRequest(
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
    status = monitors.status
    note = monitors.note
    active_conditions = monitors.active_conditions

    view = _supervisor_progress.row_view(
        request=_supervisor_progress.RowViewRequest(
            track=track,
            session=session,
            status=status,
            note=note,
            obs=obs,
            settled_streaming_progress=settled_streaming_progress,
            picker_stall=monitors.picker_stall.view,
            supervisor_state_stale=attention.supervisor_state_stale,
        )
    )
    # Re-arm edge-triggered alerts per condition, not per row: a track can stay in
    # NEEDS YOU for one reason while a different condition clears and must re-arm.
    if act:
        _supervisor_liveness.clear_alert_conditions(
            sup=sup, repo=repo, topic=topic, conditions=frozenset(active_conditions)
        )
    return view
