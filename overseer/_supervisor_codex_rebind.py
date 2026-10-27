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
import codex_sessions
import registry
import signals
from _supervisor_codex_adoption import codex_host_readers
from _supervisor_discovery_adoption import profile_for_adoption
from _supervisor_launch_profile_sources import LaunchProfileSource

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["UNIDENTIFIED_NOTE", "rebound_codex_coordinate", "unidentified_codex_pane"]

# What the operator is told about a track the daemon cannot resolve to a pane OR declare
# gone. It names the condition rather than the mechanism: the actionable fact is that a
# live Codex pane in this repository could not be identified.
UNIDENTIFIED_NOTE = "a live Codex pane in this repo resolves to no single session"


def _track_candidates(
    *, sup: Supervisor, track: registry.Track
) -> tuple[_supervisor_codex_identity.CodexPaneCarrier, ...]:
    """The exact live Codex carriers this track may claim, or no answer.

    Repository membership establishes only the first half of a join: two Codex panes in
    one repository are ordinary.  The other half is either the row's exact recorded
    identity or the state database's thread name matching the daemon-derived session
    name.  Finally, no other row may make either claim on that same session.
    """
    rows = registry.read_valid_mapping(store_path=sup.store_path)
    names = codex_sessions.read_thread_names(codex_home=sup.codex_home)
    expected = registry.tmux_id(repo=track.repo, topic=track.topic, colliding=sup.colliding_topics)
    found: list[_supervisor_codex_identity.CodexPaneCarrier] = []
    for carrier in _supervisor_codex_identity.pane_codex_carriers(
        sup=sup,
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        readers=codex_host_readers(sup=sup),
    ):
        if carrier.session_id is None or not signals.path_in_repo(
            pane_current_path=carrier.cwd, repo=track.repo
        ):
            continue
        indexed = [
            live
            for (coordinate, _name), live in sup.live_codex.items()
            if coordinate == carrier.coordinate
        ]
        if indexed and all(live.session_id != carrier.session_id for live in indexed):
            continue
        identity = f"{_supervisor_codex_identity.CODEX_IDENTITY_PREFIX}{carrier.session_id}"
        thread_matches = names.get(carrier.session_id) == expected
        if identity != track.observed_session_identity and not thread_matches:
            continue
        claiming = [
            row
            for row in rows
            if row.observed_session_identity == identity
            or names.get(carrier.session_id)
            == registry.tmux_id(repo=row.repo, topic=row.topic, colliding=sup.colliding_topics)
        ]
        if len(claiming) == 1 and (registry.norm(repo=claiming[0].repo), claiming[0].topic) == (
            registry.norm(repo=track.repo),
            track.topic,
        ):
            found.append(carrier)
    return tuple(found)


def _unidentified_carrier(
    *, sup: Supervisor, track: registry.Track
) -> _supervisor_codex_identity.CodexPaneCarrier | None:
    """One live carrier that leaves this repository's track unidentified."""
    for carrier in _supervisor_codex_identity.pane_codex_carriers(
        sup=sup,
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        readers=codex_host_readers(sup=sup),
    ):
        if carrier.session_id is None and signals.path_in_repo(
            pane_current_path=carrier.cwd, repo=track.repo
        ):
            return carrier
    return None


def report_unidentified_codex_pane(*, sup: Supervisor, track: registry.Track) -> bool:
    """Log one precise diagnostic for an unresolved live carrier, if one exists."""
    carrier = _unidentified_carrier(sup=sup, track=track)
    if carrier is None:
        return False
    condition = carrier.refusing_condition or "no live candidate"
    key = (registry.norm(repo=track.repo), track.topic, f"codex-unidentified:{carrier.pid}")
    if key not in sup.alerted:
        sup.alerted[key] = condition
        sup.log(
            message=(
                f"unidentified Codex pane {carrier.coordinate} carrier {carrier.pid}: {condition}"
            )
        )
    return True


def _record_live_codex(
    *, sup: Supervisor, track: registry.Track, carrier: _supervisor_codex_identity.CodexPaneCarrier
) -> bool:
    """Persist the live Codex identity and its complete launch profile together."""
    pane_pid = next(
        (
            pid
            for pid, coordinate in sup.tmux.pane_pid_sessions().items()
            if coordinate == carrier.coordinate
        ),
        None,
    )
    source = LaunchProfileSource(
        pid=carrier.pid,
        harness="codex",
        pane_pid=pane_pid,
        session_id=carrier.session_id,
        cwd=carrier.cwd,
    )
    profile = profile_for_adoption(
        sup=sup,
        source=source,
        session=carrier.coordinate,
        repo=track.repo,
        topic=track.topic,
    )
    if profile is None or carrier.session_id is None:
        return False
    _ = registry.record_observed_session_identity(
        repo=track.repo,
        topic=track.topic,
        session_identity=f"{_supervisor_codex_identity.CODEX_IDENTITY_PREFIX}{carrier.session_id}",
        store_path=sup.store_path,
    )
    _ = registry.record_model_profile(
        repo=track.repo, topic=track.topic, model_profile=profile, store_path=sup.store_path
    )
    return True


def rebound_codex_coordinate(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> str | None:
    """The live coordinate this row's dead tmux locator should name, or None.

    Returns None — leaving the stored coordinate exactly as it stands — for a stored
    herdr target, a row recording no Codex identity, a row whose recorded identity no
    live pane resolves to, and a row whose live pane is already the coordinate it stores.

    The STORE WRITE and its log line are gated on ``act``; the resolved coordinate is
    returned either way. The read-only `list` path classifies without mutating, and it
    still has to tell the truth about the track — it is the surface an operator reads
    before deciding whether to touch anything — so resolving in memory and writing only
    on an acting tick is what keeps both halves of that true.
    """
    candidates = _track_candidates(sup=sup, track=track)
    if len(candidates) != 1:
        return None
    carrier = candidates[0]
    coordinate = carrier.coordinate
    if act:
        if not _record_live_codex(sup=sup, track=track, carrier=carrier):
            return None
        if coordinate != session:
            _ = registry.repoint_tmux(
                repo=track.repo,
                topic=track.topic,
                new_tmux=coordinate,
                store_path=sup.store_path,
            )
            sup.log(message=f"rebound {track.repo}::{track.topic} tmux {session} → {coordinate}")
    return coordinate


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
    return _unidentified_carrier(sup=sup, track=track) is not None
