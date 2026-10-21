"""Rebind a mapped row from a DEAD TMUX locator to the pane running its Codex session.

The fleet moved from tmux to herdr on 2026-10-10, and a row assigned before that still
carries the unqualified tmux session name it was adopted under. That name now resolves
to nothing: the daemon reports the track ``session-gone`` while the session itself is
working in a herdr pane, which is what was measured on 2026-10-14 (work-item
``overseer-iffpgw``).

Adoption's own re-point (:mod:`_supervisor_herdr_moved`) cannot answer this case,
because it follows a live session the Codex INDEX can name, and the carrier here has no
rollout file descriptor for that join to work from. So the match is made against the
identity the daemon itself RECORDED on the row while that session was provably alive,
and the live side comes from :mod:`_supervisor_codex_identity` through the per-tick live
map.

**Scope is deliberately one backend shape.** Only a stored coordinate that is NOT a
herdr target is rebound here. A stored herdr target names a backend instance and a pane,
and moving it has its own rules — the renumbered-pane re-key in
:mod:`_supervisor_evaluate_target`, and the same-instance movability test in
:mod:`_supervisor_herdr_moved`. Widening this rebind to cover one would duplicate those
decisions somewhere they cannot see the transaction state they depend on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_codex_identity
import herdr_identity
import registry

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["rebound_codex_coordinate"]


def _live_coordinate(*, sup: Supervisor, track: registry.Track) -> str | None:
    """The coordinate of the live Codex pane this track's topic resolves to, if unique."""
    found = [coordinate for coordinate, topic in sup.live_codex if topic == track.topic]
    return found[0] if len(found) == 1 else None


def rebound_codex_coordinate(*, sup: Supervisor, track: registry.Track, session: str) -> str | None:
    """The live coordinate this row's dead tmux locator should name, or None.

    Returns None — leaving the stored coordinate exactly as it stands — for a stored
    herdr target, a row recording no Codex identity, a row no live pane answers for, and
    a row whose live pane is already the coordinate it stores.
    """
    if herdr_identity.decode_target(value=session).herdr is not None:
        return None
    if not (track.observed_session_identity or "").startswith(
        _supervisor_codex_identity.CODEX_IDENTITY_PREFIX
    ):
        return None
    coordinate = _live_coordinate(sup=sup, track=track)
    if coordinate is None or coordinate == session:
        return None
    _ = registry.repoint_tmux(
        repo=track.repo,
        topic=track.topic,
        new_tmux=coordinate,
        store_path=sup.store_path,
    )
    sup.log(message=f"rebound {track.repo}::{track.topic} tmux {session} → {coordinate}")
    return coordinate
