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

from typing import TYPE_CHECKING

import claude_sessions
import registry
import signals
from _supervisor_config import ACK_STALE_AFTER, CLAUDE_BUSY_STATUSES
from _supervisor_records import InjectState, Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "effective_ctx",
    "is_codex_track",
    "observe",
    "pane_is_managed",
    "pane_is_managed_claude",
]


def effective_ctx(sup: Supervisor, key: tuple[str, str], current: int | None) -> int | None:
    """Current remaining-%, or the last known if this tick read unknown.

    Design: unknown ⇒ keep last known, and unknown NEVER counts as a
    threshold crossing (so a never-known track stays None and cannot warn).
    """
    state = sup.inject.setdefault(key, InjectState())
    if current is not None:
        state.last_ctx = current
        return current
    return state.last_ctx


def is_codex_track(
    sup: Supervisor, session: str | None, repo: str, topic: str, target: str | None = None
) -> bool:
    """True iff ``target``'s pane is a live codex session for THIS plan, in THIS repo.

    TWO conditions, and BOTH are load-bearing — one is exact but session-scoped, the
    other pane-scoped but generic, and only together are they exact AND pane-scoped:

    1. ``self.live_codex`` (rebuilt each tick from real codex processes holding real
       rollouts) has a session keyed by ``(this tmux, this topic)`` whose cwd is in
       this repo. Never a guess. Keyed by ``(tmux, name)`` — not tmux alone — so a
       SECOND codex sharing this tmux session (a different topic) does not shadow this
       track's own session (#4).
    2. ``target``'s OWN pane command is codex-like. `bun` is far too generic to gate
       on alone (any bun app matches), which is why (1) exists — but it is exactly
       what makes this PANE-scoped.

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
    if not signals.path_in_repo(live.cwd, repo):
        return False
    if target is None:
        return True  # no pane to check against (callers that only have the mapping)
    return signals.pane_is_codex(sup.tmux.pane_current_command(session=target))


def pane_is_managed(
    sup: Supervisor, target: str, repo: str, topic: str, session: str | None
) -> bool:
    """The identity gate for EITHER runtime: is this pane OUR session, in OUR repo?

    Claude via the pane's own process identity + the live session's name; Codex via
    the live per-tick session map (`bun` is too generic to gate on). Fail-closed:
    anything unproven is not ours.
    """
    return pane_is_managed_claude(sup, target, repo, topic, session) or is_codex_track(
        sup, session, repo, topic
    )


def pane_is_managed_claude(
    sup: Supervisor, target: str, repo: str, topic: str, session: str | None
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
    if not signals.pane_is_claude(sup.tmux.pane_current_command(session=target)):
        return False
    if not signals.path_in_repo(sup.tmux.pane_current_path(session=target), repo):
        return False
    names = sup.claude_names_by_session.get(session or "")
    return not names or topic in names


def observe(
    sup: Supervisor, track: registry.Track, *, session: str, target: str, key: tuple[str, str]
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
    # A pane can show an empty prompt yet still be running a
    # `Bash(run_in_background)` command — that command runs as a DESCENDANT
    # shell of the pane's process. A descendant shell ⇒ active background work
    # ⇒ the session is BUSY (suppresses both injection AND restart), even
    # though the pane text looks idle. Runtime-agnostic (walks the process
    # tree, independent of any Claude-specific registry).
    pane_pid = sup.tmux.pane_pid(session=session)
    bg_shell = pane_pid is not None and claude_sessions.has_active_subshell(
        pane_pid, children_of=sup.children_of, comm_of=sup.comm_of
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
    codex_fallback = claude_status is None and bg_shell
    busy = signals.is_busy(capture) or claude_busy or codex_fallback
    gate = signals.is_structured_gate(capture)
    is_codex = is_codex_track(sup, session, repo, topic, target)
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
    idle = signals.is_codex_idle_input(capture) if is_codex else signals.is_idle_input(capture)
    # Ctx% is runtime-agnostic: `parse_ctx_remaining` matches BOTH statuslines
    # (`Ctx: N% left` / `Context N% left`), so each runtime reports ITS OWN computed
    # number and there is no occupancy formula here to get wrong.
    current_ctx = signals.parse_ctx_remaining(capture)
    eff_ctx = effective_ctx(sup, key, current_ctx)

    # Track the CONTINUOUS-idle episode for the keep-going nudge's minimum-duration gate
    # (`IDLE_NUDGE_AFTER`). A session is "cleanly idle" only at an empty prompt AND not
    # busy (busy folds in Claude's registry `busy`/`shell`, which an idle-looking capture
    # misses — a sub-agent / background command is active work). The FIRST cleanly-idle
    # tick stamps `idle_since`; ANY non-idle tick clears it, so brief activity resets the
    # clock and only a genuinely long idle spell reaches the nudge.
    istate = sup.inject.setdefault(key, InjectState())
    if idle and not busy:
        if istate.idle_since is None:
            istate.idle_since = sup.now()
    else:
        istate.idle_since = None

    stamp = registry.read_injection_stamp(repo, topic, sup.stamp_path)

    # The ONE indicator file (`ready` / `blocked` / `winding-down`). A single file
    # with a VALUE — never two presence-markers, which could both exist and whose
    # precedence was incidental rather than designed (maintainer 2026-07-14).
    declared = signals.read_state(repo, topic)
    malformed = declared is not None and not signals.valid_token(declared.token)
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
    return Observation(
        capture=capture,
        busy=busy,
        gate=gate,
        idle=idle,
        is_codex=is_codex,
        runtime=runtime,
        codex_fallback=codex_fallback,
        claude_status=claude_status,
        eff_ctx=eff_ctx,
        istate=istate,
        declared=declared,
        malformed=malformed,
        blocked=blocked,
        acked=acked,
        ready=signals.ready_valid(repo, topic, stamp),
    )
