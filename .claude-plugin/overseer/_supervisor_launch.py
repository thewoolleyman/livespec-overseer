"""_supervisor_launch — the low-level tmux-driving primitives everything composes.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This is the LEAF of the daemon's acting side: build the launch argv, respawn and
then WAIT for the pane to become the runtime it was launched as, paste and verify a
prompt actually submitted, and decide whether a pane has settled.

Nothing here decides WHETHER to act — :meth:`Supervisor.evaluate` owns that. These are
the mechanics an action is carried out with, which is why the recovery and lifecycle
collaborators both sit on top of them and why this module imports none of its siblings.

Free functions taking the ``Supervisor`` as a parameter; ``Supervisor`` is imported
under ``TYPE_CHECKING`` only, so the annotation resolves for pyright-strict while no
runtime import cycle exists.
"""

from __future__ import annotations

import shlex
import uuid
from typing import TYPE_CHECKING

import registry
import signals
from _seams import PaneCommandPredicate
from _supervisor_config import (
    RESTART_POLL_INTERVAL,
    RESTART_POLL_MAX,
    SETTLE_DELAY,
    SUBMIT_MAX_ENTERS,
    SUBMIT_POLL,
)
from _supervisor_launch_profile import claude_launch_plan, codex_launch_plan

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "await_input_box",
    "await_pane",
    "canonical_codex_session_id",
    "claude_launch_plan",
    "codex_launch_command",
    "codex_launch_plan",
    "launch_command",
    "pane_settled",
    "resend_enter",
    "session_of",
    "submit_prompt",
]


def session_of(*, sup: Supervisor, track: registry.Track) -> str:
    # A mapped track carries its real session name (`track.tmux`); only an
    # unmapped one falls back to the derived name, which must use THIS tick's
    # collision set so it matches what `start`/`auto_link` would spawn.
    return track.tmux or registry.tmux_id(
        repo=track.repo, topic=track.topic, colliding=sup.colliding_topics
    )


def canonical_codex_session_id(*, value: object) -> str | None:
    """Return a canonical UUID or ``None`` (which would open Codex's picker)."""
    if not isinstance(value, str):
        return None
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return None
    canonical = str(parsed)
    return canonical if canonical == value else None


def pane_settled(*, sup: Supervisor, target: str) -> bool:
    """True if two captures ~``SETTLE_DELAY`` apart are identical (``target`` = pane id).

    A single capture cannot distinguish active token-streaming from idle —
    the live Claude TUI renders no persistent busy spinner while streaming
    (verified 2026-07-13). Before the daemon INJECTS or RESTARTS an
    apparently-idle track, it confirms the pane is not actively changing. A
    changing pane is treated as busy (`working`) and skipped this tick —
    over-firing busy is the safe direction.
    """
    first = signals.strip_ansi(text=sup.tmux.capture_pane(session=target))
    sup.sleep(SETTLE_DELAY)
    second = signals.strip_ansi(text=sup.tmux.capture_pane(session=target))
    return first == second


def launch_command(*, track: registry.Track) -> str:
    """The Claude (re)start command: ``claude --dangerously-skip-permissions -n <topic>``.

    ``--dangerously-skip-permissions`` is REQUIRED (maintainer 2026-07-14): a
    (re)started track must resume AUTONOMOUSLY. Without it the fresh session
    stalls on the first permission prompt and the whole point of the
    auto-restart — an unattended, hands-off resume — is lost. ``-n <topic>``
    (topic shell-quoted, defensive) sets the session's display name; the resume
    line (read the handoff) is pasted AFTER launch, since a ``claude "<prompt>"``
    argv only pre-fills without submitting.

    The command deliberately carries NO tmux env scoping — no ``unset TMUX``,
    no ``TMUX_TMPDIR`` export. The former L1 env inversion (an agent-private
    socket namespace prefixed onto every spawn) was REMOVED by
    ``plan/tmux-fleet-visibility/``: it blinded every spawned agent to the real
    fleet (producing false session-liveness claims) while failing open whenever
    its tmpfs-backed directory vanished, and the L2 ``PreToolUse`` command
    guards are the layer that actually distinguishes a listing from a teardown.
    A bare ``tmux ls`` in a spawned agent MUST tell the truth; do not re-add a
    scoping prefix here.

    This is the Claude-ONLY command — it must NEVER be aimed at a codex pane (it would
    destroy the session). ``_do_restart`` dispatches a Codex track to
    :meth:`_codex_launch_command` instead.
    """
    return f"claude --dangerously-skip-permissions -n {shlex.quote(track.topic)}"


def codex_launch_command(*, session_id: str, resume: str) -> str:
    """The Codex (re)start command:
    ``codex resume --dangerously-bypass-approvals-and-sandbox <session-id> "<resume>"``.

    ``--dangerously-bypass-approvals-and-sandbox`` is the codex twin of the Claude
    path's REQUIRED ``--dangerously-skip-permissions`` (maintainer-declared 2026-07-17):
    without it the resumed session uses codex's default INTERACTIVE approval policy and
    stalls at a ``› 1.`` approval picker on its first tool call — the daemon would
    (correctly) report `blocked:human` and the "auto-restart" would not be hands-off.
    Codex documents the flag as "intended solely for environments that are externally
    sandboxed", which this local-only overseer host is (the whole fleet already runs
    `claude --dangerously-skip-permissions`).

    Resume by the exact UUID (never the name — "UUIDs take precedence" and a name can
    be ambiguous / drop to a picker), which reattaches the SAME rollout so the
    ``thread_name`` survives (adoptability). The resume line is the kick and is passed
    as the PROMPT argument, which Codex auto-submits (verified live 2026-07-17) — so
    unlike the Claude path there is no separate paste. Fields are shell-quoted; the
    flag precedes the positional ``SESSION_ID``/``PROMPT`` per ``codex resume``'s usage.

    Like :meth:`_launch_command`, this carries NO tmux env scoping — the L1
    env inversion was removed by ``plan/tmux-fleet-visibility/`` (see that
    method's docstring); do not re-add a scoping prefix here.
    """
    return (
        "codex resume --dangerously-bypass-approvals-and-sandbox "
        f"{shlex.quote(session_id)} {shlex.quote(resume)}"
    )


def await_pane(*, sup: Supervisor, target: str, is_ready: PaneCommandPredicate) -> bool:
    """Poll ``#{pane_current_command}`` until ``is_ready(cmd)``, bounded.

    ``target`` is the resolved pane id. Never scrape the ``❯``/``›`` prompt glyph
    (ambiguous shell/TUI); wait on the process identity (design). ``is_ready`` is the
    runtime predicate — :func:`signals.pane_is_claude` for a Claude restart,
    :func:`signals.pane_is_codex` for a Codex one. Returns False if it never became
    that runtime.
    """
    for _ in range(RESTART_POLL_MAX):
        if is_ready(pane_current_command=sup.tmux.pane_current_command(session=target)):
            return True
        sup.sleep(RESTART_POLL_INTERVAL)
    return False


def await_input_box(*, sup: Supervisor, target: str) -> bool:
    """Poll until the pane renders a ready (empty) Claude input box, bounded.

    Used right after a respawn, BEFORE pasting the resume line: a freshly-respawned
    Claude is often still drawing its welcome/news screen, and a paste + Enter that
    arrives then is dropped (the stranded-resume failure). Waiting for the empty `❯`
    box (`signals.input_box_ready`) means the TUI has finished its first paint and is
    ready to accept input. Best-effort — returns True if the box appeared, False if it
    never did within the bound; the caller proceeds either way (the submit-verify loop
    and the next-tick `resume_pending` retry recover a residual drop).
    """
    for _ in range(RESTART_POLL_MAX):
        if signals.input_box_ready(capture_text=sup.tmux.capture_pane(session=target)):
            return True
        sup.sleep(RESTART_POLL_INTERVAL)
    return False


def resend_enter(*, sup: Supervisor, target: str) -> bool:
    """Re-send Enter (NEVER re-paste, NEVER re-respawn) until the resume submits.

    The retry half of the self-healing resume (R1): the resume line is ALREADY sitting
    in the box from the prior respawn, so re-pasting would duplicate it — this only
    re-sends Enter, bounded by `SUBMIT_MAX_ENTERS`. Submitted is confirmed by the Claude
    box CLEARING (`signals.input_box_ready`) — the same signal `_submit_prompt` uses on
    the Claude path — NOT by the pane going busy: a freshly-respawned session can be busy
    for reasons unrelated to the resume (SessionStart hooks), so a busy check would
    false-confirm an un-submitted resume (review SF3). An extra Enter on an already-empty
    prompt is a harmless no-op.
    """
    for _ in range(SUBMIT_MAX_ENTERS):
        _ = sup.tmux.send_keys(session=target, keys="Enter")
        sup.sleep(SUBMIT_POLL)
        if signals.input_box_ready(capture_text=sup.tmux.capture_pane(session=target)):
            return True
    return False


def submit_prompt(*, sup: Supervisor, target: str, text: str, expect_codex: bool = False) -> bool:
    """Bracketed-paste a payload, then submit it — re-sending Enter until it lands.
    Returns True iff the paste LANDED and the submit is CONFIRMED. ``target`` is the
    resolved pane id (RB3).

    The paste is atomic (never fragments — blocker #2). A SINGLE Enter is
    enough on a steady idle session, but a freshly-`respawn`-ed session is
    often still drawing its welcome/news screen when the Enter arrives, and
    that first Enter is dropped — leaving the resume line un-submitted and the
    auto-restart stalled (verified live 2026-07-13). So we verify after each Enter
    and re-send up to `SUBMIT_MAX_ENTERS` times; an extra Enter on an already-empty
    prompt is a harmless no-op (neither TUI submits an empty message).

    The confirm signal is RUNTIME-SPECIFIC because the two TUIs render differently:

    - **Claude** — either the pane goes BUSY after Enter, or the empty `❯` box
      returns AFTER the pasted text was observed in the composer at least once.
    - **Codex** (`expect_codex`) — the pane goes BUSY (`signals.is_busy` matches
      Codex's `esc to interrupt` / `Working …`). Codex has no `❯` box and its empty
      box shows a grey rotating PLACEHOLDER indistinguishable from typed text in an
      ANSI-stripped capture, so "box cleared" is not a usable signal; "the model
      started responding" is (verified live 2026-07-17 — busy within ~1s of Enter).
      Caveat (adversarial review 2026-07-17): the Codex confirm reads `is_busy` over
      the whole capture, so a payload the daemon PASTES must not itself contain a
      busy-marker substring (`esc to interrupt`, `· Ns ·`, `↓ N tokens`, `(running`),
      or an UNSUBMITTED payload sitting in the composer would false-read as submitted.
      The current wrap-up / nudge / resume texts are all clear of these; keep them so.

    Returning a bool (B5): callers must know whether the payload actually
    went in. A failed ``bracketed_paste`` is a hard False — WITHOUT it the box
    would still read empty and a never-delivered wrap-up/resume would be
    counted as sent (the paste-failure false-success the maintainer flagged).
    """
    if not sup.tmux.bracketed_paste(session=target, text=text):
        sup.log(message=f"bracketed paste FAILED for pane {target}")
        return False
    sup.sleep(RESTART_POLL_INTERVAL)
    paste_visible = False
    was_busy = False
    if not expect_codex:
        capture = sup.tmux.capture_pane(session=target)
        paste_visible = signals.input_box_text(capture_text=capture) is not None
        was_busy = signals.is_busy(capture_text=capture)
    for _ in range(SUBMIT_MAX_ENTERS):
        _ = sup.tmux.send_keys(session=target, keys="Enter")
        sup.sleep(SUBMIT_POLL)
        capture = sup.tmux.capture_pane(session=target)
        if expect_codex:
            if signals.is_busy(capture_text=capture):
                return True
            continue
        busy = signals.is_busy(capture_text=capture)
        if busy and not was_busy:
            return True
        was_busy = busy
        if signals.input_box_text(capture_text=capture) is not None:
            paste_visible = True
        submitted = paste_visible and signals.input_box_ready(capture_text=capture)
        if submitted:
            return True
    return False
