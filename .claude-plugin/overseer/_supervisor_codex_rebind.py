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

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_codex_identity
import herdr_identity
import registry
import signals
from _supervisor_codex_adoption import codex_host_readers

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "UNIDENTIFIED_NOTE",
    "ReboundCodexCoordinate",
    "rebound_codex_coordinate",
    "unidentified_codex_pane",
]

# What the operator is told about a track the daemon cannot resolve to a pane OR declare
# gone. It names the condition rather than the mechanism: the actionable fact is that a
# live Codex pane in this repository could not be identified.
UNIDENTIFIED_NOTE = "a live Codex pane in this repo resolves to no single session"


@dataclass(frozen=True, kw_only=True)
class ReboundCodexCoordinate:
    """The one live Codex pane and identity a dead mapping may safely adopt."""

    coordinate: str
    identity: str


def _live_coordinate(*, sup: Supervisor, track: registry.Track) -> str | None:
    """The coordinate of the live pane running the exact session this row RECORDED.

    The topic alone is not evidence, and following it was a real defect: a restarted
    Codex session leaves the index naming a NEW rollout under the same topic while the
    row still records the predecessor, so a topic match bound the row to a session it had
    never observed. Adoption's own re-point already follows a live INDEXED session, on
    evidence this rebind does not have, so the two do not compete.
    """
    recorded = track.observed_session_identity
    found = [
        coordinate
        for (coordinate, topic), live in sup.live_codex.items()
        if topic == track.topic
        and f"{_supervisor_codex_identity.CODEX_IDENTITY_PREFIX}{live.session_id}" == recorded
    ]
    return found[0] if len(found) == 1 else None


def _same_herdr_server(*, recorded: str, candidate: str) -> bool:
    """Whether the two qualified coordinates name one Herdr server generation."""
    old = herdr_identity.decode_target(value=recorded).herdr
    new = herdr_identity.decode_target(value=candidate).herdr
    return (
        old is not None
        and new is not None
        and herdr_identity.herdr_instance_key(target=old)
        == herdr_identity.herdr_instance_key(target=new)
    )


def _named_herdr_candidate(
    *, sup: Supervisor, track: registry.Track, session: str
) -> ReboundCodexCoordinate | None:
    """The one named Codex carrier on a gone Herdr target's server, if unique."""
    if herdr_identity.decode_target(value=session).herdr is None:
        return None
    candidates = [
        ReboundCodexCoordinate(
            coordinate=coordinate,
            identity=f"{_supervisor_codex_identity.CODEX_IDENTITY_PREFIX}{live.session_id}",
        )
        for (coordinate, topic), live in sup.live_codex.items()
        if topic == track.topic
        and signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
        and _same_herdr_server(recorded=session, candidate=coordinate)
    ]
    return candidates[0] if len(candidates) == 1 else None


def rebound_codex_coordinate(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> ReboundCodexCoordinate | None:
    """The live coordinate this row's dead tmux locator should name, or None.

    Returns None — leaving the stored coordinate exactly as it stands — when neither a
    recorded Codex identity nor one named Codex carrier on the gone Herdr server can
    identify a unique successor.

    The STORE WRITE and its log line are gated on ``act``; the resolved coordinate is
    returned either way. The read-only `list` path classifies without mutating, and it
    still has to tell the truth about the track — it is the surface an operator reads
    before deciding whether to touch anything — so resolving in memory and writing only
    on an acting tick is what keeps both halves of that true.
    """
    named = _named_herdr_candidate(sup=sup, track=track, session=session)
    if named is None:
        if not (track.observed_session_identity or "").startswith(
            _supervisor_codex_identity.CODEX_IDENTITY_PREFIX
        ):
            return None
        coordinate = _live_coordinate(sup=sup, track=track)
        if coordinate is None:
            return None
        named = ReboundCodexCoordinate(
            coordinate=coordinate,
            identity=track.observed_session_identity or "",
        )
    if named.coordinate == session:
        return None
    if act:
        _ = registry.repoint_tmux(
            repo=track.repo,
            topic=track.topic,
            new_tmux=named.coordinate,
            store_path=sup.store_path,
        )
        _ = registry.record_observed_session_identity(
            repo=track.repo,
            topic=track.topic,
            session_identity=named.identity,
            store_path=sup.store_path,
        )
        sup.log(message=f"rebound {track.repo}::{track.topic} tmux {session} → {named.coordinate}")
    return named


def unidentified_codex_pane(*, sup: Supervisor, track: registry.Track) -> bool:
    """Whether a live Codex pane in this row's repository could not be identified.

    The discriminator between "this track's session is gone" and "the daemon cannot say".
    `session-gone` is an ASSERTION that the session is not there, and a live Codex
    carrier the identity chain could not resolve does not support it — so the condition
    is reported on its own terms instead.

    Scoped to a row that records a Codex identity, so a Claude track costs no scan, and
    to the row's own repository, so one unidentifiable pane cannot restate every other
    repository's genuinely-gone tracks.
    """
    if not (track.observed_session_identity or "").startswith(
        _supervisor_codex_identity.CODEX_IDENTITY_PREFIX
    ):
        return False
    return any(
        carrier.session_id is None
        and signals.path_in_repo(pane_current_path=carrier.cwd, repo=track.repo)
        for carrier in _supervisor_codex_identity.pane_codex_carriers(
            sup=sup,
            pane_pid_to_session=sup.tmux.pane_pid_sessions(),
            readers=codex_host_readers(sup=sup),
        )
    )
