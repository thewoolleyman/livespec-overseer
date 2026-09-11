"""Bringing up a VERIFIED fresh Codex session in a pane the daemon already owns.

The mechanics half of the Codex wrap-up restart. :mod:`_supervisor_codex_restart` owns
the round — what authorises a restart, and when the ``ready`` declaration may be
consumed — and delegates here for the one question that is entirely about the
successor: is there now a brand-new Codex session in this pane, adoptable under this
plan topic, running the resume line it was handed?

That question has three parts a ``codex resume`` restart never had to answer, and each
is a step below:

- **It must be a NEW rollout.** ``resume`` reattaches the predecessor's rollout AND its
  context, which is why it cannot serve a wrap-up restart at all (see that module's
  header for the live measurement). A fresh launch resets the window, and the only
  evidence available that it did is that discovery reports a DIFFERENT session id than
  the one that was live before the respawn.
- **It must be NAMED.** A fresh rollout carries no ``session_index`` ``thread_name``, so
  the daemon submits ``/rename <topic>`` — the durable half of the successor's identity,
  since that record outlives the process.
- **It must have TAKEN the resume line.** A fresh launch passes no argv prompt (the
  session has to be named before the model starts working), so the ledger-grounded
  resume line is pasted and submit-verified, exactly as on the Claude arm.

**The ORDER those are asked in is load-bearing, and getting it wrong cost the first
natural live control of this arm (2026-09-11, ``overseer-hymhx3``).** Naming used to be
confirmed through the fd-gated live join, and the resume submit was reachable only
through that proof. But the join needs a live process holding the successor's rollout
OPEN, and in the idle seconds right after the rename it can come back EMPTY — measured
live: the new carrier started at 00:19:33Z, the binary at 00:19:42Z, the index recorded
the rename at 00:19:46Z, and the join was still empty when the round gave up at
00:20:04Z with the declaration unspent and the resume line never submitted.

So each proof is now taken from evidence that exists in ITS OWN phase: the name is
confirmed from the durable ``session_index`` record (:func:`fresh_rollout_indexed`),
which is written while the successor is idle and outlives it; the resume turn is
submitted; and the fd-gated different-rollout join (:func:`fresh_rollout_live`) is proved
while Codex is EXECUTING that turn, which is precisely when a live process is holding
its rollout open. Nothing is weakened — the round still closes only on a canonical
successor rollout, in this tmux session and this repository, different from the one live
before the respawn.

Every failure here is fail-closed: it returns False having ALERTED, and the caller keeps
the ``ready`` declaration so the next tick retries rather than stranding the track.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import codex_sessions
import registry
import signals
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX, SUBMIT_MAX_ENTERS
from _supervisor_launch_profile import CodexLaunchPlan, codex_fresh_launch_plan
from _supervisor_statusline_model import (
    restart_blocked_by_statusline_mismatch as statusline_mismatch,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "bring_up_fresh_codex_session",
    "fresh_rollout_indexed",
    "fresh_rollout_live",
    "rename_command",
]


def rename_command(*, topic: str) -> str:
    """The Codex TUI slash command that persists ``topic`` as the session's thread name.

    ``/rename`` is what appends a ``thread_name`` record to ``session_index.jsonl``, and
    that record is the DURABLE half of the successor's identity: it outlives the process,
    so a daemon that is itself restarted still joins the rollout back to its plan topic.
    The live half — the mapping row already binding this tmux session — is what makes the
    fresh session adoptable within the very next tick even before the index is re-read.
    """
    return f"/rename {topic}"


def fresh_rollout_indexed(*, sup: Supervisor, track: registry.Track, prior_session_id: str) -> bool:
    """True once ``session_index`` names THIS topic on a rollout that is not the prior one.

    The naming proof that is available in the phase the naming happens: ``/rename`` appends
    the record, and the record does not depend on any process still being alive — let alone
    on one holding its rollout open, which is the fd evidence the idle successor does not
    yet supply. Among the ids the index finally names ``topic``, the most-recently-updated
    one wins, so the answer flips exactly when the rename lands on a NEW rollout rather
    than on any older namesake of the same topic.

    The id is required to be a canonical UUID for the same reason the predecessor's is
    (:func:`_supervisor_codex_restart._prior_session_id`): an id that cannot be compared
    cannot discriminate "the rollout changed" from "nothing happened".
    """
    indexed = codex_sessions.latest_session_for_thread_name(
        thread_name=track.topic, codex_home=sup.codex_home
    )
    return (
        indexed is not None
        and indexed != prior_session_id
        and _supervisor_launch.canonical_codex_session_id(value=indexed) is not None
    )


def fresh_rollout_live(
    *, sup: Supervisor, track: registry.Track, session: str, prior_session_id: str
) -> bool:
    """True once discovery reports THIS topic on a rollout that is not the prior one.

    Three facts at once, which is why it is the round's post-respawn proof: the topic
    resolves to a live Codex process (so the launch took), the session id DIFFERS from
    the one that was live before the respawn (so the rollout really is new and the
    context window really did reset), and its cwd is inside the repository.
    """
    live = sup.live_codex.get((session, track.topic))
    return (
        live is not None
        and live.session_id != prior_session_id
        and signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
    )


def _alert(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
    message: str,
    condition: str,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=message,
        condition=condition,
    )


def _launch_plan(
    *, sup: Supervisor, track: registry.Track, target: str, session: str
) -> CodexLaunchPlan | None:
    launch = codex_fresh_launch_plan(track=track, daemon_restart=True)
    if not isinstance(launch, CodexLaunchPlan):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message=f"{launch.message}; keeping the ready declaration so it retries",
            condition="stale-launch-profile",
        )
        return None
    if statusline_mismatch(sup=sup, track=track, target=target, session=session):
        return None
    return launch


def _fresh_pane(*, sup: Supervisor, track: registry.Track, target: str, session: str) -> bool:
    """Respawn the pane onto a brand-new Codex session and wait for it to accept input."""
    launch = _launch_plan(sup=sup, track=track, target=target, session=session)
    if launch is None:
        return False
    if not sup.tmux.respawn_pane(
        session=target,
        cwd=track.repo,
        command=launch.command,
        env=launch.env,
    ):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
            condition="codex-restart-respawn-failed",
        )
        return False
    if not _supervisor_launch.await_pane(sup=sup, target=target, is_ready=signals.pane_is_codex):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="respawned pane never became Codex; keeping the ready declaration",
            condition="codex-post-respawn-not-ready",
        )
        return False
    if signals.is_structured_gate(capture_text=sup.tmux.capture_pane(session=target)):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="fresh Codex pane is on a structured picker; keeping the ready declaration",
            condition="codex-fresh-picker-after-restart",
        )
        return False
    return True


def _named(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
    prior_session_id: str,
) -> bool:
    """Submit ``/rename <topic>``, then wait for the successor's NAME to be recorded.

    The confirmation is never the pane going busy: a slash command asks the model for
    nothing, so Codex's usual submit-confirm signal never fires for it. Enter is re-sent
    while the poll runs, bounded by the same ``SUBMIT_MAX_ENTERS`` budget the prompt
    submitter uses, because a freshly-respawned TUI can drop the first one; an extra Enter
    on an empty composer is a no-op.

    The DURABLE index record is asked first, because it is the evidence this phase
    actually produces. The live join is kept as the second answer for the one shape the
    index cannot speak for: a successor Codex never indexes, which the daemon still tracks
    through its store-bound binding (see :mod:`_supervisor_unindexed_codex`). Asking the
    index first also means an ordinary named restart never has to reach for fd evidence
    here at all — which is the whole point, since that is the evidence the idle successor
    does not yet supply.
    """
    if not sup.tmux.bracketed_paste(session=target, text=rename_command(topic=track.topic)):
        return False
    for attempt in range(RESTART_POLL_MAX):
        if attempt < SUBMIT_MAX_ENTERS:
            _ = sup.tmux.send_keys(session=target, keys="Enter")
        sup.sleep(RESTART_POLL_INTERVAL)
        if fresh_rollout_indexed(sup=sup, track=track, prior_session_id=prior_session_id):
            return True
        sup.refresh_codex_sessions()
        if fresh_rollout_live(
            sup=sup, track=track, session=session, prior_session_id=prior_session_id
        ):
            return True
    return False


def _adopted(
    *, sup: Supervisor, track: registry.Track, session: str, prior_session_id: str
) -> bool:
    """Wait for ORDINARY live discovery to report the successor, bounded.

    Taken last, while the submitted resume turn is executing — which is exactly when a
    live Codex process is holding its rollout open, so this is the phase the fd-gated join
    can answer. It is also the question the next tick will ask, which is why the round is
    not closed until it says yes.
    """
    for _ in range(RESTART_POLL_MAX):
        sup.refresh_codex_sessions()
        if fresh_rollout_live(
            sup=sup, track=track, session=session, prior_session_id=prior_session_id
        ):
            return True
        sup.sleep(RESTART_POLL_INTERVAL)
    return False


def bring_up_fresh_codex_session(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    prior_session_id: str,
    resume: str,
) -> bool:
    """Replace this pane with a fresh, named, kicked Codex session. False (alerted) on any miss."""
    if not _fresh_pane(sup=sup, track=track, target=target, session=session):
        return False
    if not _named(
        sup=sup,
        track=track,
        session=session,
        target=target,
        prior_session_id=prior_session_id,
    ):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message=(
                "fresh Codex session was never named for this plan topic; "
                "keeping the ready declaration"
            ),
            condition="codex-fresh-session-unnamed",
        )
        return False
    if not _supervisor_launch.submit_prompt(sup=sup, target=target, text=resume, expect_codex=True):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="fresh Codex session never took the resume line; keeping the ready declaration",
            condition="codex-fresh-resume-unsubmitted",
        )
        return False
    if not _adopted(sup=sup, track=track, session=session, prior_session_id=prior_session_id):
        _alert(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message=(
                "respawned pane has no live Codex process on a fresh rollout; "
                "keeping the ready declaration"
            ),
            condition="codex-fresh-session-unadopted",
        )
        return False
    return True
