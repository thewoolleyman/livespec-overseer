"""_supervisor_state — the round's state-file lifecycle (write, void, clear).

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. The state file is how a tracked session DECLARES itself (`ready`, `blocked`,
an ack); these functions retire a declaration that has outlived its round, so a
stale marker can never authorize an act. Every one is fail-soft: an unreadable or
absent marker voids rather than raising.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_config import MARKER_VOID_GRACE, track_key

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "clear_state",
    "delete_state_file",
    "void_if_stale",
    "void_stale_blocked",
]


def delete_state_file(*, sup: Supervisor, track: registry.Track) -> bool:
    try:
        signals.state_path(repo=track.repo, topic=track.topic).unlink(missing_ok=True)
    except OSError as exc:
        sup.log(message=f"could not delete state file for {track.repo}::{track.topic}: {exc}")
        return False
    return True


def clear_state(*, sup: Supervisor, track: registry.Track) -> None:
    """Delete a track's state file, clear its stamp, AND reset its inject state.

    Used both after a successful restart and when a session that declared ``ready``
    genuinely resumes work. ``clear_injection_stamp`` deletes the sidecar key,
    resetting BOTH the round's ``at`` and its notified bands — so after a clear (or
    a restart) the round fully resets and every escalation band can fire again in
    the next round. Clearing on the FILESYSTEM (state file + stamp) makes it durable
    across a daemon restart. It ALSO pops the in-memory ``inject`` state
    (mirroring ``_do_restart``) so the stale ``last_ctx`` does not linger; the
    next threshold crossing opens a clean round that writes a new stamp
    (adversarial code re-review 2026-07-13, blocker RB2).
    """
    _ = delete_state_file(sup=sup, track=track)
    registry.clear_injection_stamp(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
    _ = sup.inject.pop(track_key(repo=track.repo, topic=track.topic), None)


def void_if_stale(*, sup: Supervisor, track: registry.Track, ready: bool) -> bool:
    """Void a stale ``ready`` declaration on a busy tick ONLY if past the grace.

    Returns the (possibly cleared) ``ready`` flag. A declaration younger than
    ``MARKER_VOID_GRACE`` is the declaring turn's own busy tail and is LEFT
    intact (RB1); an older one means the session resumed work after declaring
    ready, so its (now false) declaration is voided.
    """
    if not ready:
        return ready
    state = signals.read_state(repo=track.repo, topic=track.topic)
    if state is None:
        return ready  # unreadable → leave it; ready_valid already gates
    age = sup.now() - state.mtime
    if age > MARKER_VOID_GRACE:
        floor_recorded = _record_ready_void(sup=sup, track=track, state=state)
        deleted = delete_state_file(sup=sup, track=track)
        if not floor_recorded and not deleted:
            sup.alert(
                repo=track.repo,
                topic=track.topic,
                session=track.tmux or registry.tmux_id(repo=track.repo, topic=track.topic),
                pane=track.tmux or registry.tmux_id(repo=track.repo, topic=track.topic),
                message="ready void failed to record its floor AND delete the declaration",
                condition="ready-void-both-writes-failed",
            )
        sup.log(
            message=f"voided stale ready declaration for {track.repo}::{track.topic} "
            f"(age {age:.0f}s > {MARKER_VOID_GRACE:.0f}s grace; session resumed work)"
        )
        return False
    return ready


def void_stale_blocked(
    *, sup: Supervisor, track: registry.Track, blocked: str | None, generating: bool
) -> str | None:
    """Void a ``blocked:`` declaration the session has outlived. Returns it, or None.

    A session that is GENERATING is, **by observation, not waiting on a human** — so a
    ``blocked:`` declaration still on disk is provably false. This is NOT the daemon
    making a semantic judgment (invariant 1): it is not guessing that the session is
    unblocked, it is reading that the session is producing tokens, which is
    incompatible with waiting for an answer.

    Why it is needed: nothing else retires a ``blocked:``. ``_clear_state`` runs only
    on the daemon's own restart path, so a pane replaced OUT-OF-BAND (a hand-restarted
    session, a `/clear`) inherits its predecessor's declaration — found live
    2026-07-16, where a fresh session rendered `working (awaiting maintainer next-step
    decision — Codex…)`, a reason written by a session that no longer existed. Left
    alone, the dead reason also fires a false ``blocked:human`` alert the moment the
    session goes idle.

    Two bounds keep it honest, each pinned by a test:

    - **``generating``, not merely ``busy``.** A session busy ONLY via a live
      ``Bash(run_in_background)`` command (Claude ``shell``) is sitting AT ITS PROMPT
      and can legitimately be awaiting a human while a build runs — not provably
      stale, so never voided however old. Only a real generation spinner or Claude
      ``busy`` (actively generating / an in-process sub-agent) qualifies.
    - **The same ``MARKER_VOID_GRACE`` as ``ready`` (RB1).** The declaring turn's own
      final text streams for 10-60s AFTER the write, so a young declaration must
      survive its own busy tail — else every legitimate declaration is destroyed
      before the pane ever goes idle.

    An idle blocked session is never touched: it keeps its declaration and keeps
    alerting, forever, until the session itself retracts it.
    """
    if blocked is None or not generating:
        return blocked
    state = signals.read_state(repo=track.repo, topic=track.topic)
    if state is None or state.token != signals.STATE_BLOCKED:
        return blocked  # unreadable, or no longer a block → leave it
    age = sup.now() - state.mtime
    if age <= MARKER_VOID_GRACE:
        return blocked  # the declaring turn's own tail (RB1)
    _ = delete_state_file(sup=sup, track=track)
    sup.log(
        message=f"voided stale blocked declaration for {track.repo}::{track.topic} "
        f"(age {age:.0f}s > {MARKER_VOID_GRACE:.0f}s grace; session resumed generating)"
    )
    return None


def _record_ready_void(
    *, sup: Supervisor, track: registry.Track, state: signals.TrackState
) -> bool:
    record = registry.read_round_record(
        repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path
    )
    if record.session_identity is not None:
        live_identity = _live_identity_for_void(sup=sup, track=track)
        if live_identity != record.session_identity:
            sup.alert(
                repo=track.repo,
                topic=track.topic,
                session=track.tmux or registry.tmux_id(repo=track.repo, topic=track.topic),
                pane=track.tmux or registry.tmux_id(repo=track.repo, topic=track.topic),
                message="ready void observed under a different session identity; floor not raised",
                condition="ready-void-identity-mismatch",
            )
            return False
    try:
        return registry.record_ready_void(
            repo=track.repo,
            topic=track.topic,
            ts=sup.now(),
            floor_min=state.mtime + MARKER_VOID_GRACE,
            stamp_path=sup.stamp_path,
        )
    except OSError as exc:
        sup.log(message=f"could not record ready void for {track.repo}::{track.topic}: {exc}")
        return False


def _live_identity_for_void(*, sup: Supervisor, track: registry.Track) -> str | None:
    session = track.tmux or registry.tmux_id(repo=track.repo, topic=track.topic)
    live = sup.live_codex.get((session, track.topic))
    if live is not None:
        return f"codex:{live.session_id}"
    identity = sup.claude_identity_by_session.get((session, track.topic))
    return identity if identity is not None else f"claude:{session}:{track.topic}"
