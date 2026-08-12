"""_supervisor_observe — phase 1 of a tick: gather every fact the cascade decides on.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Nothing here DECIDES anything and nothing here acts: each function reads a
pane, a marker or a process table and reports what it found, so that
:func:`_supervisor_evaluate.evaluate` can read as a single top-to-bottom precedence
order over already-gathered facts.

The pane-identity pair (:func:`pane_is_managed` and its Claude half) lives here for
the same reason — it answers `is this really OUR session`, which is a fact, not a
decision.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_ready
import claude_sessions
import registry
import signals
from _supervisor_config import (
    ACK_STALE_AFTER,
    CLAUDE_BUSY_STATUSES,
    CONDITION_CONTINUITY_GAP,
    CTX_STALE_AFTER,
)
from _supervisor_records import ConditionEpisode, InjectState, Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "advance_condition",
    "effective_ctx",
    "is_codex_track",
    "observe",
    "observed_stale_ctx_age",
    "pane_is_managed",
    "pane_is_managed_claude",
    "update_idle_episode",
]


def advance_condition(*, episode: ConditionEpisode, condition_now: bool, now: float) -> None:
    """Apply the single observed-condition start/reset/gap rule."""
    if condition_now:
        if episode.since is None or (
            episode.last_seen is not None and (now - episode.last_seen) > CONDITION_CONTINUITY_GAP
        ):
            episode.since = now
        episode.last_seen = now
        return
    episode.since = None
    episode.last_seen = None


def effective_ctx(
    *, sup: Supervisor, key: tuple[str, str], current: int | None, now: float
) -> int | None:
    """Current remaining-%, last known while fresh, or unknown once stale."""
    state = sup.inject.setdefault(key, InjectState())
    if current is not None:
        state.last_ctx = current
        state.last_ctx_seen = now
        advance_condition(episode=state.ctx_unreadable_episode, condition_now=False, now=now)
        return current
    if state.last_ctx is None:
        advance_condition(episode=state.ctx_unreadable_episode, condition_now=False, now=now)
        return None
    advance_condition(episode=state.ctx_unreadable_episode, condition_now=True, now=now)
    if state.last_ctx_seen is not None and (now - state.last_ctx_seen) >= CTX_STALE_AFTER:
        return None
    return state.last_ctx


def observed_stale_ctx_age(
    *, state: InjectState, current: int | None, eff_ctx: int | None, now: float
) -> float | None:
    """Age of stale last-known ctx, or None while ctx knowledge is fresh/absent."""
    if current is not None or eff_ctx is not None or state.last_ctx_seen is None:
        return None
    age = max(0.0, now - state.last_ctx_seen)
    if age < CTX_STALE_AFTER:
        return None
    return age


def update_idle_episode(*, state: InjectState, idle: bool, busy: bool, now: float) -> None:
    """Advance the continuous-idle episode used by the keep-going nudge."""
    if idle and not busy:
        if state.idle_since is None:
            state.idle_since = now
        state.idle_last_seen = now
        return
    state.idle_since = None
    state.idle_last_seen = None


def _cmdline_names_codex_launcher(*, cmdline: bytes | None) -> bool:
    """True when a process argv names the Codex launcher as an argument."""
    if cmdline is None:
        return False
    argv = [part.decode(errors="replace") for part in cmdline.split(b"\x00") if part]
    return any(Path(arg).name == "codex" for arg in argv[1:])


def _target_pane_is_codex(*, sup: Supervisor, target: str) -> bool:
    """Pane-scoped Codex evidence for ambiguous tmux foreground commands."""
    command = sup.tmux.pane_current_command(session=target)
    if signals.pane_is_codex(pane_current_command=command):
        return True
    pane_pid = sup.tmux.pane_pid(session=target) or -1
    return _cmdline_names_codex_launcher(cmdline=sup.cmdline_of(pid=pane_pid))


def is_codex_track(
    *, sup: Supervisor, session: str | None, repo: str, topic: str, target: str | None = None
) -> bool:
    """True iff ``target``'s pane is a live codex session for THIS plan, in THIS repo.

    TWO conditions, and BOTH are load-bearing — one is exact but session-scoped, the
    other pane-scoped, and only together are they exact AND pane-scoped:

    1. ``self.live_codex`` (rebuilt each tick from real codex processes holding real
       rollouts) has a session keyed by ``(this tmux, this topic)`` whose cwd is in
       this repo. Never a guess. Keyed by ``(tmux, name)`` — not tmux alone — so a
       SECOND codex sharing this tmux session (a different topic) does not shadow this
       track's own session (#4).
    2. ``target``'s OWN pane carries Codex process identity: either a codex-like
       foreground command (`bun` / `codex`) or exact argv naming the Codex launcher
       when tmux reports the foreground as ambiguous `node`. `bun` and `node` are far
       too generic to gate on alone, which is why (1) exists — but this pane read is
       what makes the exact session evidence PANE-scoped.

    **Why (2) was added (adversarial review, 2026-07-17).** With only (1) this was
    session-scoped while the Claude identity gate is pane-scoped, so ANY codex process
    resolving into a Claude track's tmux session — a `codex resume <topic>` spawned
    from INSIDE that Claude session's own Bash tool, or a codex TUI opened in a second
    window to dual-drive the same plan — reclassified the live CLAUDE track as codex.
    The consequence is now DESTRUCTIVE, not merely quiet: a Codex track is a full
    citizen (2026-07-17), so a misclassified Claude track would be restarted on its
    `ready` via `codex resume` — the WRONG-runtime respawn that destroys the live
    Claude session — and its wrap-up would be submit-verified as Codex (waiting for a
    busy pane that a Claude submit need not produce). Pane-scoping (2) closes it. The
    naming convention this very change establishes ("codex threads named after plan
    topics") is what makes the collision reachable, so this is not exotic.
    """
    live = sup.live_codex.get((session or "", topic))
    if live is None:
        return False
    # The (tmux, topic) key already pins name == topic; only the repo remains to check.
    if not signals.path_in_repo(pane_current_path=live.cwd, repo=repo):
        return False
    if target is None:
        return True  # no pane to check against (callers that only have the mapping)
    return _target_pane_is_codex(sup=sup, target=target)


def pane_is_managed(
    *, sup: Supervisor, target: str, repo: str, topic: str, session: str | None
) -> bool:
    """The identity gate for EITHER runtime: is this pane OUR session, in OUR repo?

    Claude via the pane's own process identity + the live session's name; Codex via
    the live per-tick session map (`bun` is too generic to gate on). Fail-closed:
    anything unproven is not ours.
    """
    return pane_is_managed_claude(
        sup=sup, target=target, repo=repo, topic=topic, session=session
    ) or is_codex_track(sup=sup, session=session, repo=repo, topic=topic)


def pane_is_managed_claude(
    *, sup: Supervisor, target: str, repo: str, topic: str, session: str | None
) -> bool:
    """True iff ``target``'s pane is a live Claude TUI for THIS topic, in ``repo``.

    The identity gate for EVERY act (inject / restart). ``pane_is_claude`` and
    ``path_in_repo`` exist and are tested, but the shipped daemon wired them
    only into auto-link and the restart poll, NOT the act path — so a tracked
    Claude that had exited to a shell (the pane retains the dead TUI's idle-box
    frame) would get the wrap-up pasted INTO THE SHELL, where the
    ``echo ready > …/.overseer-state`` line executes and FORGES a valid
    declaration (adversarial code review 2026-07-13, blocker B3 = Codex #1). Gating
    every act on process identity + cwd closes that, and hardens B1's residual
    (a name that resolved to the wrong session would fail the cwd check).

    **The ``topic in names`` parity check (R2, 2026-07-18).** The Codex gate is
    pane-scoped (``_is_codex_track`` requires ``live.name == topic``); the Claude gate
    was not, so a generic reused tmux window (``livespec1``…) the store maps to topic A
    but now running topic B's Claude — same repo — passed the process+cwd check and got
    A's wrap-up injected into B, then a ``ready`` respawn-KILLED B as A. Here a live Claude
    named for THIS topic must be present in this pane's tmux session
    (``self.claude_names_by_session``
    — the SET of all live Claude names in that tmux session, so a HELPER Claude sharing the
    session cannot shadow the track's own name; review SF5). Reject on POSITIVE proof that
    the tmux session has live Claude names but NOT this topic's; an UNKNOWN tmux session
    (empty set — registry miss, or a direct-``evaluate`` test that did not populate the
    map) preserves the prior process+cwd gate — fail-soft, so a transient registry miss can
    never flap a live track to ``session-gone``.

    ``target`` is the resolved pane id (RB3), so the identity read is of the
    exact pane, never a prefix-matched sibling.
    """
    if not signals.pane_is_claude(
        pane_current_command=sup.tmux.pane_current_command(session=target)
    ):
        return False
    if not signals.path_in_repo(
        pane_current_path=sup.tmux.pane_current_path(session=target), repo=repo
    ):
        return False
    names = sup.claude_names_by_session.get(session or "")
    return not names or topic in names


def observe(
    *, sup: Supervisor, track: registry.Track, session: str, target: str, key: tuple[str, str]
) -> Observation:
    """Gather every fact :meth:`evaluate`'s guard cascade decides on.

    Called only after the identity gate has proven ``target`` is our managed
    pane, so every read here is safe to perform. This method DECIDES nothing:
    it never pastes, respawns, alerts, or writes a stamp. Its one mutation is
    advancing the track's continuous-idle clock, which is part of observing
    how long the session has been idle rather than a decision about it.
    """
    repo, topic = track.repo, track.topic
    capture = sup.tmux.capture_pane(session=target)
    # A pane can show an empty prompt yet still be running a later
    # `Bash(run_in_background)` command — that command runs as a DESCENDANT shell
    # of the pane's process. The shared detector ignores startup wrapper shells
    # only when their /proc starttimes prove they belong to the runtime launch
    # chain; later or ambiguous shell evidence remains BUSY.
    pane_pid = sup.tmux.pane_pid(session=session)
    bg_shell = pane_pid is not None and claude_sessions.has_active_subshell(
        root_pid=pane_pid,
        children_of=sup.children_of,
        comm_of=sup.comm_of,
        starttime_of=sup.starttime_of,
    )
    # Claude's own live self-report is AUTHORITATIVE for an adopted Claude session,
    # and its vocabulary maps cleanly onto busy-ness (`~/.claude/sessions/<pid>.json`
    # `status`): `busy` = actively generating / running an in-process sub-agent (which
    # spawns no descendant shell, so the process-walk misses it); `shell` = at the
    # prompt with a live `Bash(run_in_background)` command — Claude's OWN, accurate
    # background-work signal; `waiting` = at a gate/prompt for the human; `idle` =
    # nothing pending. So for a session we have adopted we IGNORE the process-tree
    # shell-walk entirely and trust `status`: it is strictly better than the walk,
    # which both MISSED sub-agents (false-idle) and false-fired on lingering/transient
    # shells (false-working). `has_active_subshell` (`bg_shell`) remains ONLY the
    # runtime-agnostic FALLBACK for a session with no registry entry (Codex).
    # `claude_status is None` ⇒ not an adopted Claude session.
    claude_status = sup.claude_status_by_session.get(session)
    claude_busy = claude_status in CLAUDE_BUSY_STATUSES
    is_codex = is_codex_track(sup=sup, session=session, repo=repo, topic=topic, target=target)
    codex_fallback = claude_status is None and bg_shell and is_codex
    busy = signals.is_busy(capture_text=capture) or claude_busy or codex_fallback
    gate = signals.is_structured_gate(capture_text=capture)
    # The row's RUNTIME, derived ONCE here where `is_codex` is already known, then
    # carried onto every row below that has a live managed pane (`tmux=session`) so the
    # table's tmux column can annotate the session name (`livespec (claude)` /
    # `livespec1 (codex)`). Every branch reaching this point HAS a managed pane (the
    # no-managed-pane / unassigned rows returned above with `tmux=None` and no runtime),
    # so `claude`/`codex` is always the right binary answer here.
    runtime = "codex" if is_codex else "claude"
    # `is_idle_input` knows CLAUDE's prompt: an EMPTY `❯` between two rules. Codex's
    # prompt is a `›` line above its statusline (`… · Context N% left · …`), so it
    # needs its own STRUCTURAL detector (`is_codex_idle_input`) — NOT the coarse
    # "not busy". A Codex track is now a full citizen that gets the wrap-up pasted in
    # and is restarted on `ready`, so this gate is load-bearing: an over-loose idle
    # read would let a booting pane or a Codex approval/trust picker (`› 1.`) be
    # keystroked into. Structural idle keeps that impossible (a picker is a gate; a
    # blank/booting pane has no `›`+statusline shape → `settling`, re-read next tick).
    idle = (
        signals.is_codex_idle_input(capture_text=capture)
        if is_codex
        else signals.is_idle_input(capture_text=capture)
    )
    # Ctx% is runtime-agnostic: `parse_ctx_remaining` matches BOTH statuslines
    # (`Ctx: N% left` / `Context N% left`), so each runtime reports ITS OWN computed
    # number and there is no occupancy formula here to get wrong.
    now = sup.now()
    istate = sup.inject.setdefault(key, InjectState())
    current_ctx = signals.parse_ctx_remaining(capture_text=capture)
    previous_ctx = istate.last_ctx
    ctx_changed = (
        current_ctx is not None and previous_ctx is not None and current_ctx != previous_ctx
    )
    eff_ctx = effective_ctx(sup=sup, key=key, current=current_ctx, now=now)
    if ctx_changed:
        istate.last_ctx_changed_at = now

    # Track the CONTINUOUS-idle episode for the keep-going nudge's minimum-duration gate
    # (`IDLE_NUDGE_AFTER`). A session is "cleanly idle" only at an empty prompt AND not
    # busy (busy folds in Claude's registry `busy`/`shell`, which an idle-looking capture
    # misses — a sub-agent / background command is active work). The FIRST cleanly-idle
    # tick stamps `idle_since`; ANY non-idle tick clears it, so brief activity resets the
    # clock and only a genuinely long idle spell reaches the nudge.
    update_idle_episode(state=istate, idle=idle, busy=busy, now=now)
    ctx_stale_age = observed_stale_ctx_age(
        state=istate, current=current_ctx, eff_ctx=eff_ctx, now=now
    )
    stale_ctx = istate.last_ctx if ctx_stale_age is not None else None

    # The ONE indicator file (`ready` / `blocked` / `winding-down`). A single file
    # with a VALUE — never two presence-markers, which could both exist and whose
    # precedence was incidental rather than designed (maintainer 2026-07-14).
    declared = signals.read_state(repo=repo, topic=topic)
    malformed = declared is not None and not signals.valid_token(token=declared.token)
    blocked = (
        declared.detail or "(no reason given)"
        if declared is not None and declared.token == signals.STATE_BLOCKED
        else None
    )
    acked = (
        declared is not None
        and declared.token == signals.STATE_WINDING_DOWN
        and (sup.now() - declared.mtime) <= ACK_STALE_AFTER
    )
    round_obs = _supervisor_ready.round_observation(
        sup=sup,
        repo=repo,
        topic=topic,
        session=session,
        runtime=runtime,
        declared=declared,
    )
    return Observation(
        capture=capture,
        busy=busy,
        gate=gate,
        idle=idle,
        is_codex=is_codex,
        runtime=runtime,
        codex_fallback=codex_fallback,
        claude_status=claude_status,
        current_ctx=current_ctx,
        eff_ctx=eff_ctx,
        ctx_changed=ctx_changed,
        ctx_stale_age=ctx_stale_age,
        stale_ctx=stale_ctx,
        injection_stamp=round_obs.record.at,
        round_record=round_obs.record,
        session_identity=round_obs.session_identity,
        ready_uncertifiable_reason=round_obs.ready_uncertifiable_reason,
        istate=istate,
        declared=declared,
        malformed=malformed,
        blocked=blocked,
        acked=acked,
        ready=round_obs.ready,
    )
