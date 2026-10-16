"""_supervisor_nudge_marker — the daemon's own ``idle-with-context-left`` marker.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This is the ONE token the daemon writes to itself, and the write/clear pair
here is what makes the keep-going nudge single-shot per idle episode: the marker is
written when a nudge lands, read by the idle branch as "already nudged", and cleared
the moment the session leaves the episode, re-arming a later one.

It lives apart from :mod:`_supervisor_nudge` because the nudge ACT is no longer its
only writer. A held channel delivery (v060) can be released as DELIVERED a tick or
more after it was sent, and that release owes the episode the same marker a landed
paste writes — but the release is driven from the evaluation's reconcile phase, not
from the act. Keeping the marker beside the act would have made the hold's side of
the contract reach back through the module that consults the hold.

Nothing here decides WHETHER a nudge is owed; that judgement stays in the cascade's
idle branch. These are only the three ways the marker's lifetime begins and ends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_state
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "clear_idle_nudge_state",
    "record_nudge_episode_answered",
    "write_idle_nudge_state",
]


def write_idle_nudge_state(*, sup: Supervisor, track: registry.Track) -> None:
    """Write the daemon-owned ``idle-with-context-left`` marker to the state file.

    Called ONLY after a nudge delivery lands, and ONLY when the file had no session
    declaration (guarded in :meth:`evaluate` for the act, and by
    :func:`record_nudge_episode_answered` for a released hold), so it can never
    overwrite a ``ready`` / ``blocked`` / ``winding-down``. It edge-triggers the
    single-prompt-per-episode rule and drives the row's ``idle-with-context-left``
    status.
    """
    path = signals.state_path(repo=track.repo, topic=track.topic)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(signals.STATE_IDLE_WITH_CONTEXT_LEFT + "\n", encoding="utf-8")
    except OSError as exc:
        sup.log(message=f"could not write idle-nudge marker for {track.repo}::{track.topic}: {exc}")


def record_nudge_episode_answered(*, sup: Supervisor, track: registry.Track) -> None:
    """Mark the episode a RELEASED keep-going nudge answered, as a landed paste does.

    The wrap-up's never-again record is its notified bands, which the hold itself
    carries and :mod:`_supervisor_channel_hold` writes. The nudge's is this marker,
    and a hold released as DELIVERED owes it exactly as a landed delivery does —
    without it the freed track re-enters the idle branch with the episode unmarked
    and is nudged AGAIN on the very tick the channel confirmed the first one.

    Guarded, where the act's own write has no need to be: a release runs in the
    tick's PROLOGUE rather than inside the idle branch, so the session may have
    declared `ready` / `blocked` / `winding-down` / `done` since the nudge was sent,
    and the one token the daemon writes to itself must never overwrite one it does
    not own.
    """
    current = signals.read_state(repo=track.repo, topic=track.topic)
    if current is not None and signals.valid_session_token(token=current.token):
        return
    write_idle_nudge_state(sup=sup, track=track)


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
