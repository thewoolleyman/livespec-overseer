"""_supervisor_nudge — the idle-with-context nudge and the non-responder alert.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Both surfaces exist for a session that is NOT in trouble the daemon can fix
by restarting it: one keeps an idle session going, the other escalates a session
that has stopped answering as its context runs out. The nudge marker's own
write/clear pair lives here too, since it is what makes the nudge single-shot per
idle episode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_prompts import (
    charter_authorized_unblock_nudge_message,
    idle_nudge_message,
    supervisor_idle_nudge_message,
)
from _supervisor_records import InjectState

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "alert_non_responder",
    "clear_idle_nudge_state",
    "nudge_charter_authorized_picker_stall",
    "nudge_idle_with_context",
    "write_idle_nudge_state",
]


def write_idle_nudge_state(*, sup: Supervisor, track: registry.Track) -> None:
    """Write the daemon-owned ``idle-with-context-left`` marker to the state file.

    Called ONLY after the nudge paste lands, and ONLY when the file had no session
    declaration (guarded in :meth:`evaluate`), so it can never overwrite a ``ready`` /
    ``blocked`` / ``winding-down``. It edge-triggers the single-prompt-per-episode rule
    and drives the row's ``idle-with-context-left`` status.
    """
    path = signals.state_path(repo=track.repo, topic=track.topic)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(signals.STATE_IDLE_WITH_CONTEXT_LEFT + "\n", encoding="utf-8")
    except OSError as exc:
        sup.log(message=f"could not write idle-nudge marker for {track.repo}::{track.topic}: {exc}")


def clear_idle_nudge_state(*, sup: Supervisor, track: registry.Track) -> None:
    """Clear the ``idle-with-context-left`` marker when the session leaves the idle
    episode (it went non-idle / took a turn) — re-arming a fresh nudge next episode.

    Re-reads the file immediately before replacing it and writes a diagnostic ONLY if
    it is still the daemon's own marker, so a ``ready`` / ``blocked`` the session wrote
    in the same tick is never clobbered. Unlike :meth:`_clear_state` it touches neither
    the injection stamp nor the in-memory inject state — the nudge opens no round.
    """
    current = signals.read_state(repo=track.repo, topic=track.topic)
    if current is None or current.token != signals.STATE_IDLE_WITH_CONTEXT_LEFT:
        return
    if _supervisor_state.write_state_diagnostic(
        sup=sup,
        track=track,
        token=signals.STATE_IDLE_NUDGE_CLEARED,
        detail="session left idle episode; idle-with-context-left marker cleared",
    ):
        sup.log(
            message=(
                f"cleared idle-with-context-left marker for {track.repo}::{track.topic} "
                "(session left idle episode)"
            )
        )


def nudge_idle_with_context(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    eff_ctx: int,
    threshold: int,
    is_codex: bool = False,
) -> None:
    """Send the single "keep going" nudge to an idle session that still has context
    left, and — only if the paste lands — write the ``idle-with-context-left`` marker
    so it fires at most ONCE per idle episode.

    The inverse of :meth:`_maybe_inject`: it fires ABOVE the threshold to keep a session
    from stopping early, not below it to wind one down. The marker is written AFTER a
    successful submit (as ``_maybe_inject`` marks its bands only on success), so a
    failed paste re-nudges next tick rather than silently marking the episode handled.

    ``is_codex`` selects the runtime-appropriate submit verification (a Codex submit is
    confirmed by the pane going busy, not by a cleared ``❯`` box).
    """
    repo, topic = track.repo, track.topic
    if isinstance(track, registry.SupervisorSeat):
        message = supervisor_idle_nudge_message(
            remaining=eff_ctx,
            threshold=threshold,
            repo=repo,
            topic=track.supervised_topic,
            epic=track.epic,
        )
    else:
        message = idle_nudge_message(
            remaining=eff_ctx,
            threshold=threshold,
            repo=repo,
            topic=topic,
            epic=track.epic,
        )
    if _supervisor_launch.submit_prompt(
        sup=sup, target=target, text=message, expect_codex=is_codex
    ):
        write_idle_nudge_state(sup=sup, track=track)
        sup.log(
            message=f"nudged idle-with-context-left {repo}::{topic} "
            f"(ctx {eff_ctx}% > threshold {threshold}%)"
        )
    else:
        sup.alert(
            repo=repo,
            topic=topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="idle-with-context-left nudge FAILED (paste did not land); will retry",
            condition="idle-nudge-submit-failed",
        )


def nudge_charter_authorized_picker_stall(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    stall_seconds: int,
    istate: InjectState,
) -> None:
    """Paste a charter reminder into a stalled supervisor picker without submitting it."""
    if istate.picker_stall_nudged:
        return
    message = charter_authorized_unblock_nudge_message()
    if sup.tmux.bracketed_paste(session=target, text=message):
        istate.picker_stall_nudged = True
        echoed = sup.tmux.capture_pane(session=target)
        istate.picker_stall_nudge_echo_capture = echoed or None
        sup.log(
            message=(
                f"nudged charter-authorized picker stall {track.repo}::{track.topic} "
                f"({stall_seconds}s)"
            )
        )
        return
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message="charter-authorized picker-stall nudge FAILED (paste did not land)",
        condition="picker-stall-nudge-failed",
    )


def alert_non_responder(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    eff_ctx: int,
    declared: signals.TrackState | None,
) -> None:
    """Report a track deep in the danger band that is not honouring the protocol.

    This is the WHOLE response to such a session: the daemon SAYS SO, loudly, with
    the coordinates to go fix it — and does nothing else. It does NOT restart it
    (maintainer 2026-07-14: "NEVER forcibly restart a session that is not ready; it
    MUST drop the indicator file for action"), because a timer cannot know whether a
    session is safe to kill.

    Two ways to get here, and the report must not conflate them (they need different
    fixes):

    - **declared nothing at all** — the session ignored an escalating wrap-up (once
      per 10% band, insistent from 30%) telling it to ACK immediately. A session bug.
    - **a STALE ``winding-down``** — it DID acknowledge, then never finished; the ACK
      aged out of ``ACK_STALE_AFTER``. It is hung mid-wrap-up, not deaf.

    Either way this is a DEFECT REPORT about that session, not a chore for the
    operator to work around: the fix is to make the session honour the protocol,
    never to have the overseer guess on its behalf.
    """
    repo, topic = track.repo, track.topic
    if declared is not None and declared.token == signals.STATE_WINDING_DOWN:
        age = sup.now() - declared.mtime
        what = (
            f"ACKNOWLEDGED the wrap-up {age:.0f}s ago but never finished "
            f"(stale `{signals.STATE_WINDING_DOWN}`; it is hung mid-wrap-up)"
        )
    else:
        what = (
            f"has declared NOTHING (no {signals.state_path(repo=repo, topic=topic).name}) — "
            f"it is ignoring the wrap-up protocol"
        )
    sup.alert(
        repo=repo,
        topic=topic,
        session=session,
        pane=pane,
        message=(
            f"NOT RESPONDING — ctx {eff_ctx}% left and it {what}. The overseer will "
            f"NOT restart it: only the session may authorize that. A human must act."
        ),
        condition="danger-non-responder",
    )
