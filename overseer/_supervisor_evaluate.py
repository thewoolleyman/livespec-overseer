"""_supervisor_evaluate — phase 2 of a tick: the decision cascade.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module is ONE function, the decision cascade itself; the single leg
extracted from it lives in :mod:`_supervisor_resume_retry`. Everything
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

import _supervisor_launch
import _supervisor_liveness
import _supervisor_nudge
import _supervisor_observe
import _supervisor_offer
import _supervisor_progress
import _supervisor_restart
import _supervisor_state
import registry
import signals
from _supervisor_config import (
    DANGER_CTX_REMAINING,
    IDLE_NUDGE_AFTER,
    track_key,
)
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

    Extracting the fact-gathering was a real seam and is done; it took the
    function from 106 statements / 38 branches / complexity 34 down to 83 / 33
    / 31. Going further would mean cutting the cascade itself into per-state
    helpers, which was considered and rejected (maintainer-declared
    2026-07-19): it would scatter the precedence order across call sites where
    no reader can check it in one pass, and precedence is exactly what a
    reviewer of this function needs to verify. The four complexity rules are
    therefore suppressed HERE, on this one function, rather than for the file
    or the folder — every other function in this module is still held to them.

    **The one authorised exception, and its exact bounds.** ONE leg — R1, the
    self-healing resume retry — is a function
    (:func:`_supervisor_resume_retry.resume_retry`), maintainer-declared
    2026-07-26. The 2026-07-19 ruling protects the readability of the precedence
    ORDER, and that survives: the call sits at exactly the position the block
    occupied, so the cascade still reads top-to-bottom in one pass. What moved
    is that leg's DETAIL, not its place in the order. The ground was measured,
    not stylistic — this function plus its imports could not otherwise clear the
    200 LLOC SOFT ceiling, and the soft band is what fails a release. That leg
    began directly below this function and now lives in its OWN module; why, and
    what the second move cost, is on that module's header. NO OTHER leg may be
    cut out on this precedent: a ruling protects its STATED property, so the
    test for any future extraction is whether the precedence order still reads
    in one pass here, not whether it resembles this one.
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
    if busy:
        status = "working"
        if act:
            # A GENERATING session is not waiting on a human, so a `blocked:` it has
            # outlived is provably dead — retire it before the note is derived, or the
            # dead reason rides this row (it is the note default) and later fires a
            # false `blocked:human`. Busy via a BACKGROUND SHELL alone does NOT qualify:
            # that session is at its prompt and may genuinely still be waiting.
            blocked = _supervisor_state.void_stale_blocked(
                sup=sup,
                track=track,
                blocked=blocked,
                generating=signals.is_busy(capture_text=capture) or claude_status == "busy",
            )
            blocked_age = _supervisor_liveness.blocked_age(sup=sup, declared=declared)
            blocked_age_label = _supervisor_liveness.age_label_or_none(seconds=blocked_age)
            note = blocked_note(blocked=blocked, blocked_age_label=blocked_age_label)
        # When the PANE itself looks idle, the row note explains WHY it is `working`,
        # or the operator would read the idle-looking pane and distrust the status.
        if not signals.is_busy(capture_text=capture):
            if claude_status == "shell" or codex_fallback:
                note = _supervisor_liveness.append_note(
                    note=note if malformed else None,
                    extra="background shell",
                )  # a live `Bash(run_in_background)` command
            # Provably always True where it stands: reaching here needs `busy` True
            # with `is_busy(capture)` False and the `shell`/codex-fallback arm above
            # already excluded, which leaves `claude_busy` as the only disjunct that
            # can be carrying `busy` — and `CLAUDE_BUSY_STATUSES` holds exactly
            # {"busy", "shell"}. So the else-exit is dead and branch coverage can
            # never close it.
            #
            # KEPT as an `elif` rather than demoted to `else` precisely because that
            # proof depends on the CURRENT contents of `CLAUDE_BUSY_STATUSES`, which
            # exists to be extended. Add a third status and `else` would silently
            # label it "sub-agent (Claude busy)" — wrong; the `elif` correctly leaves
            # the note unset. The dead arc is the cost of that safety, so it is
            # annotated rather than removed.
            elif claude_status == "busy":  # pragma: no branch
                note = _supervisor_liveness.append_note(
                    note=note if malformed else None,
                    extra="sub-agent (Claude busy)",
                )  # in-process sub-agent, no shell
        if act:
            # Void the certification ONLY if it is past the grace — a young
            # marker is the certifying turn's own busy tail and must survive
            # (RB1); an old one means the session resumed work after certifying.
            ready = _supervisor_state.void_if_stale(sup=sup, track=track, ready=ready)
            # The session took a turn — clear any idle-with-context-left nudge marker
            # so the NEXT idle-with-context episode re-nudges (re-arm on non-idle).
            _supervisor_nudge.clear_idle_nudge_state(sup=sup, track=track)
    elif gate or blocked is not None:
        status = "blocked:human"
        if act:
            ready = _supervisor_state.void_if_stale(sup=sup, track=track, ready=ready)
            # A gate / block is also "non-idle" — drop a stale nudge marker (safe: the
            # helper re-reads and leaves a session-written `blocked` untouched).
            _supervisor_nudge.clear_idle_nudge_state(sup=sup, track=track)
            detail = blocked if blocked else "structured gate on pane"
            # The decision belongs to the TRACKED session, which is already showing
            # it in its own pane. The overseer NOTIFIES and hands over coordinates;
            # it never re-asks the question itself (invariant 8).
            active_conditions.update(
                _supervisor_liveness.surface_blocked_alerts(
                    request=_supervisor_liveness.BlockedAlertRequest(
                        sup=sup,
                        track=track,
                        session=session,
                        pane=target,
                        detail=detail,
                        declaration_mtime=declared.mtime
                        if blocked is not None and declared
                        else None,
                        blocked_age=blocked_age if blocked is not None else None,
                        blocked_age_label=blocked_age_label if blocked is not None else None,
                        istate=istate,
                    )
                )
            )
        else:
            active_conditions.add("blocked-human")
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
        if act:
            sup.alert(
                repo=repo,
                topic=topic,
                session=session,
                pane=target,
                message=(
                    f"context unreadable for "
                    f"{_supervisor_liveness.age_label(seconds=ctx_stale_age)} "
                    f"after last known {stale_ctx}% at or below {threshold}% — "
                    "inspect the pane before acting"
                ),
                condition="ctx-stale",
            )
    elif eff_ctx is not None and eff_ctx <= threshold:
        # A FRESH `winding-down` ACK buys patience: the session heard us and is
        # wrapping up, so stop re-warning (never keystroke into a session that is
        # actively winding down). A STALE ACK resumes escalating — an ACK must not
        # become an infinite stall — but still never authorizes an act.
        if act and not acked:
            _supervisor_restart.maybe_inject(
                sup=sup,
                track=track,
                target=target,
                eff_ctx=eff_ctx,
                threshold=threshold,
                is_codex=is_codex,
            )
        if acked:
            status = "winding-down"
        elif eff_ctx <= DANGER_CTX_REMAINING:
            status = "danger"
            active_conditions.add("default")
            if act:
                _supervisor_nudge.alert_non_responder(
                    sup=sup,
                    track=track,
                    session=session,
                    pane=target,
                    eff_ctx=eff_ctx,
                    declared=declared,
                )
        else:
            status = "warned"
    else:
        if not signals.topic_reserved_for_supervisor(topic=topic):
            _supervisor_offer.surface_supervision_offer(sup=sup, track=track, act=act)
        # Idle at an empty prompt with the context ABOVE the wind-down threshold. If
        # the session has declared nothing, nudge it ONCE this episode to keep going
        # rather than stop early (the inverse of the wrap-up). The daemon-written
        # `idle-with-context-left` marker makes it single-prompt; it clears when the
        # session next goes non-idle, re-arming a fresh nudge for the next episode.
        nudged_already = (
            declared is not None and declared.token == signals.STATE_IDLE_WITH_CONTEXT_LEFT
        )
        has_context_left = eff_ctx is not None and eff_ctx > threshold
        # Claude's own `waiting` = at a gate/prompt for the human. Even when no
        # structured gate is visible in the capture (it scrolled, or it is a prose
        # question a YOLO session cannot raise as a prompt), that IS "a blocking
        # question for the human" — so it must NOT be nudged to keep going.
        waiting_on_human = claude_status == "waiting"
        # `eff_ctx is not None` is spelled out here as well as inside
        # `has_context_left` so the type checker can narrow it for the
        # `_nudge_idle_with_context` call below. It is not redundant to a reader
        # either: a nudge needs a KNOWN remaining-context percentage to quote.
        if (
            eff_ctx is not None
            and has_context_left
            and not waiting_on_human
            and (declared is None or nudged_already)
        ):
            status = "idle-with-context-left"
            # Fire the nudge ONLY after the session has been continuously idle for at
            # least `IDLE_NUDGE_AFTER` (maintainer 2026-07-18: the nudge was "too
            # aggressive, TOO SOON", interrupting sessions merely between turns). The
            # status still reads `idle-with-context-left` immediately (it is descriptive,
            # not an attention row); only the keystroke waits for the 1-hour floor.
            idle_long_enough = (
                istate.idle_since is not None
                and (sup.now() - istate.idle_since) >= IDLE_NUDGE_AFTER
            )
            if act and not nudged_already and idle_long_enough:
                _supervisor_nudge.nudge_idle_with_context(
                    sup=sup,
                    track=track,
                    target=target,
                    eff_ctx=eff_ctx,
                    threshold=threshold,
                    is_codex=is_codex,
                )
        else:
            status = "idle"

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
