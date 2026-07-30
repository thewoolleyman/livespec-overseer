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
import _supervisor_ctx_stale
import _supervisor_idle
import _supervisor_launch
import _supervisor_liveness
import _supervisor_observe
import _supervisor_offer
import _supervisor_progress
import _supervisor_restart
import _supervisor_threshold
import registry
import signals
from _supervisor_config import track_key
from _supervisor_resume_retry import resume_retry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["evaluate"]


def evaluate(  # noqa: C901, PLR0912, PLR0915 — see "On the size of this function"
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
    if track.is_unassigned:
        return RowView(topic=track.topic, repo=track.repo, tmux=None, ctx=None, status="unassigned")

    repo, topic = track.repo, track.topic
    session = _supervisor_launch.session_of(sup=sup, track=track)
    key = track_key(repo=repo, topic=topic)

    if not sup.tmux.session_exists(session=session):
        # The mapped TMUX session is gone — but the work may not be. A Claude
        # session for the same plan can keep running in a NON-tmux terminal (a bare
        # SSH shell), which the tmux-only daemon cannot capture, inject, or respawn.
        # Distinguish that live-but-unmanageable case from a genuinely gone track so
        # the operator is not falsely alarmed that finished-looking work was lost.
        return _supervisor_offer.no_managed_pane_row(sup=sup, repo=repo, topic=topic)

    # Resolve the pane id ONCE and target every subsequent pane op by it (RB3).
    # A pane id is exact and never prefix/fnmatch-matched, so if the tracked
    # session dies mid-tick the ops fail-soft instead of a bare `-t <name>`
    # falling back to a live SIBLING session (e.g. dead `livespec--overseer`
    # resolving to live `livespec--overseer-rewrite`) and, worst case,
    # `respawn-pane -k` killing it. Stable across respawn.
    target = sup.tmux.pane_id(session=session)
    if target is None:
        return _supervisor_offer.no_managed_pane_row(sup=sup, repo=repo, topic=topic)

    # Identity gate (B3): the mapped session exists, but before reading its pane
    # for any ACT we confirm it is really OUR Claude in OUR repo — never
    # keystroke into a shell / wrong session / human split-pane.
    if not _supervisor_observe.pane_is_managed(
        sup=sup, target=target, repo=repo, topic=topic, session=session
    ):
        # The gate stays exactly what it was — an ACT guard (never keystroke into a
        # pane not proven ours). What changed is that its answer is no longer a row
        # STATUS of its own. Whether the pane is a bare shell (our session exited) or
        # something foreign, the fact for the operator is identical and simple: this
        # track's session is NOT IN THIS TMUX. It was assigned to something once, so
        # it is `session-gone` — never `unassigned`, which is reserved for a plan
        # whose session we have NEVER seen (maintainer-declared 2026-07-17: "KEEP
        # session-gone if you've ever seen the session, only use unassigned if you've
        # never seen it"). The MAPPING ROW is precisely that memory of having seen it,
        # which is why it is kept rather than pruned.
        #
        # `not-claude` is DELETED (maintainer-declared 2026-07-17: "What the hell is
        # not-claude?"). It was this gate's return value leaking into the UI — it named
        # a check's output, not anything an operator needs — and it made a bare
        # terminal (`livespec1`) look like a tracked pane while no OTHER bare terminal
        # appears at all. The daemon lists PLANS, not panes: a tmux name reaches the
        # table only as a mapping's column value, and `_no_managed_pane_row` already
        # reports `tmux=None` so no dead terminal is named.
        return _supervisor_offer.no_managed_pane_row(sup=sup, repo=repo, topic=topic)

    # Phase 1 — OBSERVE. Every fact the guard cascade below decides on is
    # gathered in one place, so the cascade reads as a single top-to-bottom
    # precedence order. Unpacked into locals so each guard reads the same way
    # it always has.
    obs = _supervisor_observe.observe(sup=sup, track=track, session=session, target=target, key=key)
    capture, busy, gate, idle = obs.capture, obs.busy, obs.gate, obs.idle
    is_codex, codex_fallback = obs.is_codex, obs.codex_fallback
    claude_status, eff_ctx, istate = obs.claude_status, obs.eff_ctx, obs.istate
    injection_stamp = obs.injection_stamp
    ctx_stale_age, stale_ctx = obs.ctx_stale_age, obs.stale_ctx
    declared, malformed, blocked, acked, ready = (
        obs.declared,
        obs.malformed,
        obs.blocked,
        obs.acked,
        obs.ready,
    )

    # Phase 2 — DECIDE.
    settled_streaming_progress = False
    active_conditions: set[str] = set()

    # R1 — self-healing resume retry. The cascade's FIRST leg, and it stays first:
    # it must intercept before the busy/idle cascade below, because a box holding the
    # un-submitted resume text reads as "not idle" and would otherwise fall to
    # `settling` and never retry. Its detail lives in `_supervisor_resume_retry`; the
    # call sits at the leg's exact position so the precedence order still reads
    # top-to-bottom here in one pass.
    retry = resume_retry(sup=sup, track=track, obs=obs, act=act, session=session, target=target)
    if retry is not None:
        return retry

    # A per-track override (an int ``ctx_threshold``) wins; otherwise inherit
    # the daemon-wide default (``warn_percent``, set from ``--warn-percent``).
    threshold = _supervisor_liveness.threshold_for(sup=sup, track=track)

    blocked_age = _supervisor_liveness.blocked_age(sup=sup, declared=declared)
    blocked_age_label = _supervisor_liveness.age_label_or_none(seconds=blocked_age)
    blocked_note = _supervisor_liveness.blocked_note
    attention = _supervisor_attention.observe_liveness_attention(
        request=_supervisor_attention.ObserveRequest(
            sup=sup,
            istate=istate,
            capture=capture,
            claude_status=claude_status,
            codex_fallback=codex_fallback,
            eff_ctx=eff_ctx,
            threshold=threshold,
            injection_stamp=injection_stamp,
        )
    )
    generating = attention.generating
    shell_only = attention.shell_only

    # The row note defaults to the blocked reason with declaration age (if any); the
    # busy branch overrides it to "background shell" when a live background shell is
    # the SOLE reason the pane isn't idle, so the operator can see WHY.
    note: str | None = blocked_note(blocked=blocked, blocked_age_label=blocked_age_label)
    ctx_stale_note = (
        f"ctx unreadable ({_supervisor_liveness.age_label(seconds=ctx_stale_age)})"
        if ctx_stale_age is not None
        else None
    )
    if malformed and declared is not None:
        active_conditions.add("malformed-state")
        note = f"BAD state file: {declared.token!r}"
        if act:
            sup.alert(
                repo=repo,
                topic=topic,
                session=session,
                pane=target,
                message=(
                    f"MALFORMED state file: {declared.token!r} is not one of "
                    f"{', '.join(signals.STATE_TOKENS)} — treated as no declaration "
                    f"(the track will NOT be restarted)"
                ),
                condition="malformed-state",
            )

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
    elif busy and not ((gate or blocked is not None) and not generating):
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
                ready=ready,
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
                ready=ready,
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
    elif not idle:
        # Pane present but not a verified idle-input state and not busy —
        # a transient/settling capture. Wait; never act.
        status = "settling"
    elif act and not _supervisor_launch.pane_settled(sup=sup, target=target):
        # One frame looks idle, but the pane is actively changing (streaming).
        settled_streaming_progress = True
        status = "working"
    elif act and not _supervisor_observe.pane_is_managed(
        sup=sup, target=target, repo=repo, topic=topic, session=session
    ):
        # TOCTOU re-check (Codex re-review #1): the identity gate ran at the top
        # of the tick, but capturing + the settle delay opened a window in which
        # the pane could have exited to a shell (or cd'd out of the repo). Re-
        # verify identity IMMEDIATELY before any act, so a wrap-up is never
        # pasted into — nor a respawn aimed at — a pane no longer proven ours.
        #
        # `settling` (a one-tick "wait and re-read"), NOT a status of its own: the
        # pane changed UNDER US mid-tick, which is exactly what settling means. The
        # act is suppressed either way, and the next tick re-enters at the top gate,
        # which classifies the settled truth (`session-gone` if it really has gone).
        status = "settling"
    elif ready:
        # The session DECLARED `ready`. This is the ONLY path to a restart — the
        # daemon never infers it (maintainer 2026-07-14). RUNTIME-DISPATCHED: for a
        # Codex track `_do_restart` routes to `codex resume <id>`, NEVER the claude
        # launch command — aiming `claude -n <topic>` at a codex pane would REPLACE
        # the codex session with a claude one and destroy it. That routing (not a
        # separate monitor-only refusal) is what preserves the one place a bug here is
        # destructive rather than merely wrong; the sabotage-verified guard test pins
        # it. A Codex track is now a full citizen (maintainer-declared 2026-07-17):
        # it is restarted on its own `ready` exactly like a Claude one.
        status = "restarting"
        if act:
            _supervisor_restart.do_restart(sup=sup, track=track, target=target, is_codex=is_codex)
    elif uncertifiable_ready is not None:
        status = "ready-uncertifiable"
        note, ready_conditions = uncertifiable_ready
        active_conditions.update(ready_conditions)
    elif ctx_stale_age is not None and stale_ctx is not None and stale_ctx <= threshold:
        status = "ctx-stale"
        active_conditions.add("ctx-stale")
        note = _supervisor_liveness.append_note(note=note, extra=ctx_stale_note)
        _supervisor_ctx_stale.ctx_stale(
            request=_supervisor_ctx_stale.CtxStaleRequest(
                sup=sup,
                track=track,
                session=session,
                pane=target,
                ctx_stale_age=ctx_stale_age,
                stale_ctx=stale_ctx,
                threshold=threshold,
                act=act,
            )
        )
    elif eff_ctx is not None and eff_ctx <= threshold:
        threshold_decision = _supervisor_threshold.threshold(
            request=_supervisor_threshold.ThresholdRequest(
                sup=sup,
                track=track,
                session=session,
                target=target,
                eff_ctx=eff_ctx,
                threshold=threshold,
                acked=acked,
                declared=declared,
                act=act,
                is_codex=is_codex,
                istate=istate,
            )
        )
        status = threshold_decision.status
        active_conditions.update(threshold_decision.active_conditions)
    else:
        status = _supervisor_idle.idle_room(
            request=_supervisor_idle.IdleRequest(
                sup=sup,
                track=track,
                target=target,
                topic=topic,
                eff_ctx=eff_ctx,
                threshold=threshold,
                declared=declared,
                claude_status=claude_status,
                istate=istate,
                act=act,
                is_codex=is_codex,
            )
        )

    if status != "ctx-stale":
        note = _supervisor_liveness.append_note(note=note, extra=ctx_stale_note)

    view = _supervisor_progress.row_view(
        track=track,
        session=session,
        status=status,
        note=note,
        obs=obs,
        settled_streaming_progress=settled_streaming_progress,
    )
    # Re-arm edge-triggered alerts per condition, not per row: a track can stay in
    # NEEDS YOU for one reason while a different condition clears and must re-arm.
    if act:
        _supervisor_liveness.clear_alert_conditions(
            sup=sup, repo=repo, topic=topic, conditions=frozenset(active_conditions)
        )
    return view
