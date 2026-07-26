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
import registry
import signals
from _supervisor_prompts import idle_nudge_message

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "alert_non_responder",
    "clear_idle_nudge_state",
    "nudge_idle_with_context",
    "write_idle_nudge_state",
]


def write_idle_nudge_state(sup: Supervisor, track: registry.Track) -> None:
    """Write the daemon-owned ``idle-with-context-left`` marker to the state file.

    Called ONLY after the nudge paste lands, and ONLY when the file had no session
    declaration (guarded in :meth:`evaluate`), so it can never overwrite a ``ready`` /
    ``blocked`` / ``winding-down``. It edge-triggers the single-prompt-per-episode rule
    and drives the row's ``idle-with-context-left`` status.
    """
    path = signals.state_path(track.repo, track.topic)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(signals.STATE_IDLE_WITH_CONTEXT_LEFT + "\n", encoding="utf-8")
    except OSError as exc:
        sup.log(f"could not write idle-nudge marker for {track.repo}::{track.topic}: {exc}")


def clear_idle_nudge_state(sup: Supervisor, track: registry.Track) -> None:
    """Clear the ``idle-with-context-left`` marker when the session leaves the idle
    episode (it went non-idle / took a turn) — re-arming a fresh nudge next episode.

    Re-reads the file immediately before unlinking and removes it ONLY if it is still
    the daemon's own marker, so a ``ready`` / ``blocked`` the session wrote in the same
    tick is never clobbered. Unlike :meth:`_clear_state` it touches neither the
    injection stamp nor the in-memory inject state — the nudge opens no round.
    """
    current = signals.read_state(track.repo, track.topic)
    if current is None or current.token != signals.STATE_IDLE_WITH_CONTEXT_LEFT:
        return
    try:
        signals.state_path(track.repo, track.topic).unlink(missing_ok=True)
    # The ONLY uncovered branch in this module, and deliberately so. The read
    # above returns unless the marker is a readable regular file, so every
    # root-proof way to make `unlink` fail (a directory at the path, a file
    # where the parent should be) also makes that read return None and returns
    # first. What remains is a permission-denied PARENT — and CI runs its
    # container steps as root, where chmod denies nothing. A test would pass
    # locally and silently stop exercising this in CI, which is worse than no
    # test. Its sibling in `_clear_state` unlinks with no preceding read, so
    # that one IS covered (a directory there yields EISDIR for every uid).
    except OSError as exc:  # pragma: no cover
        sup.log(f"could not clear idle-nudge marker for {track.repo}::{track.topic}: {exc}")


def nudge_idle_with_context(
    sup: Supervisor,
    track: registry.Track,
    target: str,
    eff_ctx: int,
    threshold: int,
    *,
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
    message = idle_nudge_message(remaining=eff_ctx, threshold=threshold, repo=repo, topic=topic)
    if _supervisor_launch.submit_prompt(sup, target, message, expect_codex=is_codex):
        write_idle_nudge_state(sup, track)
        sup.log(
            f"nudged idle-with-context-left {repo}::{topic} "
            f"(ctx {eff_ctx}% > threshold {threshold}%)"
        )
    else:
        sup.alert(
            repo=repo,
            topic=topic,
            session=_supervisor_launch.session_of(sup, track),
            pane=target,
            message="idle-with-context-left nudge FAILED (paste did not land); will retry",
        )


def alert_non_responder(
    sup: Supervisor,
    track: registry.Track,
    *,
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
            f"has declared NOTHING (no {signals.state_path(repo, topic).name}) — "
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
    )
