"""Reconciling a fresh Codex successor that only became discoverable AFTER the round gave up.

The residual failure mode of the fresh-Codex wrap-up restart, measured on that arm's
first natural live control (2026-09-11, ``overseer-bdhxhx``). Daemon instance
``685abc9a…`` launched rollout ``01a08dd5…`` at 00:19:33Z to replace predecessor
``01a08cf6…``, alerted ``codex-fresh-session-unadopted`` at 00:20:04Z when the bounded
live-adoption poll ran out, and — correctly — kept the predecessor's ``ready``
declaration and left the round open. The successor then became live and was adopted by
ordinary discovery, which is exactly the proof the round had been waiting for. Nothing
consumed it. The stale declaration stood until it expired at 03:51:31Z, the expiry
notice reset the idle episode, and a human relayed the plan-resume instruction by hand
at 03:56:59Z.

So the round's last proof is no longer the only place it can be taken. The restart
records what it launched (:mod:`_registry_codex_restart`), and an ORDINARY later tick
re-proves that record against live discovery: same indexed topic, same tracked tmux
pane, inside the same repository, on a canonical rollout that is the very successor the
``/rename`` named and is not the predecessor. Only then is the round completed —
delivering any still-undelivered resume line once, consuming the predecessor's
declaration, and closing the round so the successor's own idle-nudge and wrap-up
bookkeeping start clean.

**The recorded successor id is what makes this safe, and it is why a bare
"the identity changed" test would not be.** A pane whose Codex identity changed
out-of-band — a hand-restarted session, an operator ``/rename``, a crash-recovered
rollout — also presents a canonical, in-repo, different-rollout session under this
topic. That candidate proves a change happened; it does not prove the DAEMON made it,
and consuming a ``ready`` declaration on it would spend the cardinal rule's sole
authorization on a session the daemon never launched and never handed a resume line to.
Every candidate that is not the recorded successor is therefore refused, declaration and
round untouched, exactly as every other unproven step on this arm is.

This runs BEFORE the tick gathers its observation, deliberately: the cascade decides on
facts read at the top of :func:`_supervisor_evaluate.evaluate`, so a declaration
consumed afterwards would still be seen as armed and could drive a SECOND respawn —
killing the successor this very function just proved. Reconciling first means the same
tick observes the round already closed and classifies the successor on its own merits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_state
import codex_sessions
import registry
import signals
from _registry_codex_restart import CodexFreshRestart

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["reconcile_late_codex_successor"]

LATE_RESUME_UNSUBMITTED = "codex-late-adoption-resume-unsubmitted"


def _proven_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
    record: CodexFreshRestart,
) -> codex_sessions.CodexSession | None:
    """The live Codex session that IS this round's daemon-launched successor, or None.

    Five facts, all required, each of which a wrong candidate fails on its own: the
    restart happened in the tmux session and pane being evaluated now; discovery names
    this topic on a live rollout there; that rollout is canonical and is neither the
    predecessor nor any other id than the one the rename named; and its cwd is inside
    the track's repository. Anything less is not evidence the daemon made this change.
    """
    if record.tmux != session or record.pane != target:
        return None
    if registry.norm(repo=record.repo) != registry.norm(repo=track.repo):
        return None
    live = sup.live_codex.get((session, track.topic))
    if live is None or live.name != track.topic:
        return None
    canonical = _supervisor_launch.canonical_codex_session_id(value=live.session_id)
    if canonical is None or canonical == record.predecessor or canonical != record.successor:
        return None
    if not signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo):
        return None
    return live


def _deliver_pending_resume(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
    record: CodexFreshRestart,
) -> bool:
    """Submit a resume line this round never delivered, at most once. True if delivered.

    A record that already says the resume was delivered is left alone — that is the
    at-most-once bound, and it is what keeps a late reconciliation from pasting a
    second copy of the kick into a successor already working on the first. A submit
    that cannot be CONFIRMED marks nothing: the round stays open under its own
    diagnostic so the next tick retries, rather than consuming the declaration for a
    turn the successor never took.
    """
    if record.resume_submitted:
        return True
    if not _supervisor_launch.submit_prompt(
        sup=sup, target=target, text=record.resume, expect_codex=True
    ):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=(
                "late-adopted fresh Codex session never took the resume line; "
                "keeping the ready declaration"
            ),
            condition=LATE_RESUME_UNSUBMITTED,
        )
        return False
    registry.mark_codex_fresh_restart_resume_submitted(
        repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path
    )
    return True


def reconcile_late_codex_successor(
    *, sup: Supervisor, track: registry.Track, session: str, target: str, act: bool
) -> bool:
    """Complete a recorded fresh-Codex restart whose successor only now became live."""
    if not act:
        return False
    record = registry.read_codex_fresh_restart(
        repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path
    )
    if record is None:
        return False
    if (
        _proven_successor(sup=sup, track=track, session=session, target=target, record=record)
        is None
    ):
        return False
    if not _deliver_pending_resume(
        sup=sup, track=track, session=session, target=target, record=record
    ):
        return False
    sup.log(
        message=(
            f"late fresh Codex successor adopted for {track.repo}::{track.topic} "
            f"(pane {target}; {record.predecessor} -> {record.successor})"
        )
    )
    # Consumes the declaration, deletes the stamp key (round, bands and the provenance
    # record with it) and pops the in-memory inject state, so the successor's idle
    # episode and wrap-up bookkeeping start clean rather than inheriting its
    # predecessor's.
    _supervisor_state.clear_state(
        sup=sup,
        track=track,
        diagnostic_token=signals.STATE_RESTARTED,
        diagnostic_detail="late successor adoption completed; consumed ready declaration",
    )
    sup.log(message=f"consumed ready declaration for {track.repo}::{track.topic}")
    sup.log(message=f"restarted (codex) {track.repo}::{track.topic} (pane {target})")
    return True
