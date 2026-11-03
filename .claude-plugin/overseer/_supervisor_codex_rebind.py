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
import codex_sessions
import herdr_identity
import registry
import signals
from _supervisor_codex_adoption import codex_host_readers
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "UNIDENTIFIED_NOTE",
    "UnidentifiedCodexPane",
    "ambiguous_rebind_row",
    "rebound_codex_coordinate",
    "unidentified_codex_pane",
]

# What the operator is told about a track the daemon cannot resolve to a pane OR declare
# gone. It names the condition rather than the mechanism: the actionable fact is that a
# live Codex pane in this repository could not be identified.
UNIDENTIFIED_NOTE = "a live Codex pane in this repo resolves to no single session"
_AMBIGUOUS_CANDIDATE_COUNT = 2


@dataclass(frozen=True, kw_only=True)
class UnidentifiedCodexPane:
    """The live carrier that prevents the daemon from naming a mapped Codex track."""

    coordinate: str
    pid: int
    condition: str


@dataclass(frozen=True, kw_only=True)
class ReboundCodexCoordinate:
    """One pane and identity to which a dead mapping can safely move."""

    coordinate: str
    identity: str


def _same_herdr_server(*, recorded: str, candidate: str) -> bool:
    """Whether two coordinates belong to the same live Herdr server generation."""
    old = herdr_identity.decode_target(value=recorded).herdr
    new = herdr_identity.decode_target(value=candidate).herdr
    return (
        old is not None
        and new is not None
        and herdr_identity.herdr_instance_key(target=old)
        == herdr_identity.herdr_instance_key(target=new)
    )


def _pane_label(*, coordinate: str) -> str:
    """The backend pane identifier an operator can locate in a rebind log."""
    target = herdr_identity.decode_target(value=coordinate).herdr
    return target.pane_id if target is not None else coordinate


def _herdr_rebind_candidates(
    *, sup: Supervisor, track: registry.Track, session: str
) -> tuple[ReboundCodexCoordinate, ...]:
    """Exactly named, repository-bound Codex carriers on a dead pane's server.

    This deliberately asks the per-carrier reader rather than the adopted live map.
    The latter is a consequence of mapping ownership and could therefore hide the
    repository, database, exact-thread-name, or other-track binding evidence this
    pane-gone rebind itself has to establish.
    """
    if herdr_identity.decode_target(value=session).herdr is None or sup.tmux.session_exists(
        session=session
    ):
        return ()
    derived = registry.tmux_id(repo=track.repo, topic=track.topic, colliding=sup.colliding_topics)
    readers = codex_host_readers(sup=sup)
    names = codex_sessions.read_thread_names(
        codex_home=readers.codex_home
        if readers.codex_home is not None
        else codex_sessions.default_codex_home()
    )
    own = (registry.norm(repo=track.repo), track.topic)
    bound = {
        (row.tmux, row.observed_session_identity)
        for row in registry.read_valid_mapping(store_path=sup.store_path)
        if (registry.norm(repo=row.repo), row.topic) != own
    }
    by_pane: dict[str, set[str]] = {}
    for carrier in _supervisor_codex_identity.pane_codex_carriers(
        sup=sup,
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        readers=readers,
    ):
        if (
            carrier.session_id is None
            or names.get(carrier.session_id) != derived
            or not signals.path_in_repo(pane_current_path=carrier.cwd, repo=track.repo)
            or not _same_herdr_server(recorded=session, candidate=carrier.coordinate)
        ):
            continue
        identity = f"{_supervisor_codex_identity.CODEX_IDENTITY_PREFIX}{carrier.session_id}"
        if (carrier.coordinate, identity) in bound or any(
            carrier.coordinate == coordinate or identity == observed
            for coordinate, observed in bound
        ):
            continue
        by_pane.setdefault(carrier.coordinate, set()).add(identity)
    # Cardinality is per pane. A pane whose carriers disagree on the session is not a
    # single qualifying pane, so it is not a candidate at all.
    return tuple(
        ReboundCodexCoordinate(coordinate=coordinate, identity=next(iter(identities)))
        for coordinate, identities in sorted(by_pane.items())
        if len(identities) == 1
    )


def ambiguous_rebind_row(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> RowView | None:
    """Surface more than one qualifying successor without changing the mapping."""
    candidates = _herdr_rebind_candidates(sup=sup, track=track, session=session)
    if len(candidates) < _AMBIGUOUS_CANDIDATE_COUNT:
        return None
    panes = ", ".join(_pane_label(coordinate=candidate.coordinate) for candidate in candidates)
    note = f"ambiguous qualifying Codex panes: {panes}"
    # This is a classification only. The list path must expose the same ambiguity
    # without writes or notifications, and the candidate panes are already in its note.
    _ = act
    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=None,
        ctx=None,
        status="unidentified-session",
        note=note,
        runtime="codex",
    )


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


def _legacy_rebound_candidate(
    *, sup: Supervisor, track: registry.Track, session: str
) -> ReboundCodexCoordinate | None:
    """The existing recorded-identity rebind for a dead, unqualified tmux session."""
    if herdr_identity.decode_target(value=session).herdr is not None or not (
        track.observed_session_identity or ""
    ).startswith(_supervisor_codex_identity.CODEX_IDENTITY_PREFIX):
        return None
    coordinate = _live_coordinate(sup=sup, track=track)
    if coordinate is None:
        return None
    return ReboundCodexCoordinate(
        coordinate=coordinate, identity=track.observed_session_identity or ""
    )


def rebound_codex_coordinate(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> ReboundCodexCoordinate | None:
    """The live coordinate this row's dead locator should name, or None.

    A dead Herdr pane is rebound only to one carrier on its same server generation
    whose active state database binds its session to this repository and whose thread
    name exactly equals this track's derived session name. Legacy dead tmux locators
    retain their recorded-identity rebind path.

    The STORE WRITE and its log line are gated on ``act``; the resolved coordinate is
    returned either way. The read-only `list` path classifies without mutating, and it
    still has to tell the truth about the track — it is the surface an operator reads
    before deciding whether to touch anything — so resolving in memory and writing only
    on an acting tick is what keeps both halves of that true.
    """
    candidates = _herdr_rebind_candidates(sup=sup, track=track, session=session)
    rebound = (
        candidates[0]
        if len(candidates) == 1
        else _legacy_rebound_candidate(sup=sup, track=track, session=session)
    )
    if rebound is None or rebound.coordinate == session:
        return None
    if act:
        _ = registry.repoint_tmux(
            repo=track.repo,
            topic=track.topic,
            new_tmux=rebound.coordinate,
            store_path=sup.store_path,
        )
        _ = registry.record_observed_session_identity(
            repo=track.repo,
            topic=track.topic,
            session_identity=rebound.identity,
            store_path=sup.store_path,
        )
        sup.log(
            message=(
                f"rebound {track.repo}::{track.topic} pane "
                f"{_pane_label(coordinate=session)} → {_pane_label(coordinate=rebound.coordinate)} "
                f"({session} → {rebound.coordinate})"
            )
        )
    return rebound


def unidentified_codex_pane(
    *, sup: Supervisor, track: registry.Track
) -> UnidentifiedCodexPane | None:
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
        return None
    if _live_coordinate(sup=sup, track=track) is not None:
        return None
    for carrier in _supervisor_codex_identity.pane_codex_carriers(
        sup=sup,
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        readers=codex_host_readers(sup=sup),
    ):
        if carrier.session_id is not None or not signals.path_in_repo(
            pane_current_path=carrier.cwd, repo=track.repo
        ):
            continue
        condition = (
            "ambiguous repository sessions"
            if len(carrier.candidate_session_ids) > 1
            else "no live candidate"
        )
        return UnidentifiedCodexPane(
            coordinate=carrier.coordinate,
            pid=carrier.pid,
            condition=condition,
        )
    return None
