"""Codex-specific restart arm for the overseer supervisor.

**A wrap-up restart launches a FRESH Codex session; only crash recovery resumes.**

This arm used to respawn ``codex resume <id> "<kick>"``, the same command
:mod:`_supervisor_codex_recovery` uses. That made it a no-op for the one thing it
exists to do: ``resume`` reattaches the prior rollout AND the context that rollout
accumulated, so a restart authorised by a ``ready`` declaration CONSUMED the
declaration and handed the successor back the same nearly-exhausted window its
predecessor had just wound down out of. Measured live on ``fix-git-email``
2026-09-10 — one rollout id resumed four times while remaining context fell from 50%
to 17%, until Codex compacted itself.

So the wrap-up arm now respawns a brand-new ``codex`` session, which is the parity the
Claude arm has always had (``claude … -n <topic>`` starts a new session; the Claude
restart has never passed ``--resume``). Naming that successor, proving discovery
re-adopted it, and submitting the resume line are the MECHANICS of doing so and live in
:mod:`_supervisor_codex_fresh`; this module owns the ROUND — what authorises a restart,
and when the ``ready`` declaration may be consumed.

Crash recovery is deliberately untouched: :mod:`_supervisor_codex_recovery` still
resumes the exact persisted rollout, because restoring the conversation a crash
interrupted is the correct outcome there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_codex_fresh import bring_up_fresh_codex_session
from _supervisor_config import track_key
from _supervisor_prompts import resume_for_track

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["do_codex_restart"]


def _prior_session_id(
    *, sup: Supervisor, track: registry.Track, session: str, target: str
) -> str | None:
    """The canonical UUID of the session live in this pane RIGHT NOW, or None (alerted).

    It is no longer a command ARGUMENT — a fresh launch takes no positional — but it is
    still an INTERLOCK input: it is what the post-respawn proof compares the successor's
    rollout against. A blank or non-canonical value cannot discriminate "the rollout
    changed" from "nothing happened", so the restart is refused before ``respawn-pane``
    kills a cleanly-ready session.
    """
    live = sup.live_codex.get((session, track.topic))
    if live is None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="codex session vanished before restart; keeping the ready declaration",
            condition="codex-session-vanished-before-restart",
        )
        return None
    canonical = _supervisor_launch.canonical_codex_session_id(value=live.session_id)
    if canonical is None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=(
                "codex restart refused: live session has no valid UUID; "
                "keeping the ready declaration"
            ),
            condition="codex-restart-invalid-session-id",
        )
    return canonical


def do_codex_restart(*, sup: Supervisor, track: registry.Track, target: str) -> None:
    """Atomic restart of a CODEX track: respawn a FRESH `codex`, name it, submit the resume."""
    session = _supervisor_launch.session_of(sup=sup, track=track)
    prior_session_id = _prior_session_id(sup=sup, track=track, session=session, target=target)
    if prior_session_id is None:
        return
    resume = resume_for_track(track=track)
    if resume is None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="ready cannot respawn: no plan epic recorded",
            condition="restart-plan-epic-missing",
        )
        return
    sup.log(
        message=(
            f"codex restart dispatch {track.repo}::{track.topic} "
            f"(pane {target}; fresh session replacing {prior_session_id}; resume {resume!r})"
        )
    )
    if not bring_up_fresh_codex_session(
        sup=sup,
        track=track,
        target=target,
        session=session,
        prior_session_id=prior_session_id,
        resume=resume,
    ):
        return
    _supervisor_state.clear_state(
        sup=sup,
        track=track,
        diagnostic_token=signals.STATE_RESTARTED,
        diagnostic_detail="restart completed; consumed ready declaration",
    )
    _ = sup.inject.pop(track_key(repo=track.repo, topic=track.topic), None)
    sup.log(message=f"consumed ready declaration for {track.repo}::{track.topic}")
    sup.log(message=f"restarted (codex) {track.repo}::{track.topic} (pane {target})")
