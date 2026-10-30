"""A live Codex thread named AROUND a track's topic is surfaced as misnamed, never adopted.

Adoption joins a Codex track to a session only on an EXACT thread-name match, and the
`/rename <topic>` binding is a daemon-only step: a seat launched any other way (a
coordinator relaunch, a hand restart) is auto-titled by Codex from its first prompt, and
that title routinely CONTAINS the topic (`Resume <topic>`). Measured 2026-10-26, the
daemon then read the live seat as ``session-gone``, which is indistinguishable from a
dead one and names no cause.

Containment of the topic is evidence for the OPERATOR and never an identity. This module
therefore only REPORTS: it replaces a ``session-gone`` row with ``codex-track-misnamed``,
naming each candidate's pane, thread id and actual name plus the one-line repair, and it
acts on nothing -- no adoption, wrap-up, nudge, restart, or ready consumption. Exact-name
adoption stays the only way a session becomes a track, so the round after the thread's
index name becomes exactly the derived session name, ordinary adoption applies.

A candidate is a thread that

- a live Codex process in the track's repository runs (cwd containment, not the name);
- the Codex session index names with a string that CONTAINS the derived session name
  (case-sensitively) without EQUALING it;
- does not end in a reserved suffix, does not equal another discovered track's derived
  session name, and is not already adopted by or bound to another track.

The candidate's own runtime is what makes this a Codex case, not the track's recorded
launch profile, so a stale recorded harness does not suppress the row.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_codex_identity
import _supervisor_diagnostics
import _supervisor_discovery
import _supervisor_offer
import codex_sessions
import pane_router_coordinates
import registry
import signals
from _supervisor_codex_adoption import codex_host_readers
from _supervisor_config import track_key
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "MISNAMED_STATUS",
    "MisnamedCandidate",
    "gone_row",
    "misnamed_candidates",
    "misnamed_row",
    "rearm_misnamed_alert",
]

MISNAMED_STATUS = "codex-track-misnamed"


@dataclass(frozen=True, kw_only=True)
class MisnamedCandidate:
    """One live Codex thread that contains, but does not equal, a track's session name."""

    coordinate: str
    session_id: str
    name: str


def _live_threads(*, sup: Supervisor) -> dict[str, tuple[str, str]]:
    """``{session id: (coordinate, cwd)}`` for every live Codex thread this tick can see.

    The per-tick map answers for carriers that hold their own rollout file open; the
    identity chain adds the Codex 0.16x carriers that hold none (a shared app-server owns
    the rollouts), so a seat relaunched under either topology is found.
    """
    live: dict[str, tuple[str, str]] = {}
    for (coordinate, _name), session in sup.live_codex.items():
        _ = live.setdefault(session.session_id, (coordinate, session.cwd))
    for carrier in _supervisor_codex_identity.pane_codex_carriers(
        sup=sup,
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        readers=codex_host_readers(sup=sup),
    ):
        if carrier.session_id is not None:
            _ = live.setdefault(carrier.session_id, (carrier.coordinate, carrier.cwd))
    return live


def _derived_name(*, sup: Supervisor, repo: str, topic: str) -> str:
    return registry.tmux_id(repo=repo, topic=topic, colliding=sup.colliding_topics)


def _other_track_names(*, sup: Supervisor, track: registry.Track) -> frozenset[str]:
    own = (registry.norm(repo=track.repo), track.topic)
    discovered = registry.discover_plans(watch_repos=_supervisor_discovery.resolve_watch(sup=sup))
    mapped = registry.read_valid_mapping(store_path=sup.store_path)
    pairs = {(repo, topic) for repo, topic in discovered} | {
        (row.repo, row.topic) for row in mapped
    }
    return frozenset(
        _derived_name(sup=sup, repo=repo, topic=topic)
        for repo, topic in pairs
        if (registry.norm(repo=repo), topic) != own
    )


def misnamed_candidates(*, sup: Supervisor, track: registry.Track) -> tuple[MisnamedCandidate, ...]:
    """The live Codex threads whose index name contains, but is not, this track's session name."""
    derived = _derived_name(sup=sup, repo=track.repo, topic=track.topic)
    home = Path(sup.codex_home) if sup.codex_home else codex_sessions.default_codex_home()
    near = {
        session_id: name
        for session_id, name in codex_sessions.read_thread_names(codex_home=home).items()
        if derived in name
        and name != derived
        and not signals.topic_reserved_for_supervisor(topic=name)
    }
    if not near:
        return ()
    others = _other_track_names(sup=sup, track=track)
    bound = [
        row
        for row in registry.read_valid_mapping(store_path=sup.store_path)
        if (registry.norm(repo=row.repo), row.topic)
        != (registry.norm(repo=track.repo), track.topic)
    ]
    found: list[MisnamedCandidate] = []
    for session_id, (coordinate, cwd) in _live_threads(sup=sup).items():
        name = near.get(session_id)
        if name is None or name in others:
            continue
        if not signals.path_in_repo(pane_current_path=cwd, repo=track.repo):
            continue
        identity = f"{_supervisor_codex_identity.CODEX_IDENTITY_PREFIX}{session_id}"
        if any(
            row.tmux == coordinate or row.observed_session_identity == identity for row in bound
        ):
            continue
        found.append(MisnamedCandidate(coordinate=coordinate, session_id=session_id, name=name))
    return tuple(sorted(found, key=lambda candidate: candidate.session_id))


def _pane_label(*, coordinate: str) -> str:
    herdr = pane_router_coordinates.herdr_attention(coordinate=coordinate)
    return coordinate if herdr is None else herdr.display


def _note(*, derived: str, candidates: tuple[MisnamedCandidate, ...]) -> str:
    named = "; ".join(
        f"pane {_pane_label(coordinate=c.coordinate)} thread {c.session_id} is named {c.name!r}"
        for c in candidates
    )
    return f"/rename {derived} in the intended pane — {named}"


def misnamed_row(*, sup: Supervisor, track: registry.Track, act: bool) -> RowView | None:
    """The ``codex-track-misnamed`` row replacing this track's ``session-gone`` row, or None.

    The notification is edge-triggered on the misnamed CONDITION plus the SET of candidate
    thread ids: a candidate whose name merely changes (and still contains the topic) does
    not re-notify, a changed set does, and the entry is dropped when the condition ends.
    """
    candidates = misnamed_candidates(sup=sup, track=track)
    if not candidates:
        return None
    derived = _derived_name(sup=sup, repo=track.repo, topic=track.topic)
    note = _note(derived=derived, candidates=candidates)
    first = candidates[0].coordinate
    if act:
        _supervisor_diagnostics.alert(
            request=_supervisor_diagnostics.AlertRequest(
                sup=sup,
                repo=track.repo,
                topic=track.topic,
                session=first,
                pane=sup.tmux.pane_id(session=first),
                message=f"live Codex thread not named for this track: {note}",
                condition=MISNAMED_STATUS,
                identity=json.dumps([MISNAMED_STATUS, [c.session_id for c in candidates]]),
            )
        )
    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=first,
        ctx=None,
        status=MISNAMED_STATUS,
        note=note,
        runtime="codex",
    )


def rearm_misnamed_alert(*, sup: Supervisor, track: registry.Track, act: bool) -> None:
    """Forget the notification once the condition has ended, so its return notifies again."""
    if act:
        _ = sup.alerted.pop((*track_key(repo=track.repo, topic=track.topic), MISNAMED_STATUS), None)


def gone_row(*, sup: Supervisor, track: registry.Track, session: str, act: bool) -> RowView:
    """The no-managed-pane row, with a `session-gone` verdict swapped for the misnamed row.

    `session-gone` asserts the session is not there. When a live Codex thread in the
    track's repository CONTAINS the derived session name without equaling it, that is
    false, and the row says so. Every other row passes through untouched, and any outcome
    other than the misnamed row re-arms the notification.
    """
    row = _supervisor_offer.no_managed_pane_row(sup=sup, track=track, session=session)
    if row.status == "session-gone":
        misnamed = misnamed_row(sup=sup, track=track, act=act)
        if misnamed is not None:
            return misnamed
    rearm_misnamed_alert(sup=sup, track=track, act=act)
    return row
