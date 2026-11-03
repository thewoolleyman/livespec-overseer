"""Initial target resolution for the supervisor evaluation cascade."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, cast

import _supervisor_codex_misnamed
import _supervisor_codex_rebind
import _supervisor_herdr_moved
import _supervisor_herdr_stall
import _supervisor_launch
import _supervisor_unidentified_codex
import herdr_identity
import registry
from _supervisor_managed_target import EvaluateTarget, evaluate_managed_target
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["EvaluateTarget", "resolve_evaluate_target"]


def _unavailable_target(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> RowView:
    recovery = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup,
        track=track,
        target=session,
        act=False,
        alert=act,
    )
    if recovery is not None:
        return recovery
    return _supervisor_codex_misnamed.gone_row(sup=sup, track=track, session=session, act=act)


def _unresolved_target(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    act: bool,
    refuses_recorded_target: bool,
) -> RowView:
    """Route a track whose pane could not be resolved, honoring its own replacement.

    The one pane the recorded-identity gate must not refuse is the daemon's OWN durable
    replacement at the recorded pane: its successor is by construction a new process
    generation, so it can never match the predecessor identity the row still records.
    The transaction names the exact backend generation and pane, which
    `reconcile_bare_shell` verifies before acting, so it is reconciled with this tick's
    real `act` rather than read-only.

    The unidentifiable-Codex condition is ruled out before this helper, because every
    route below ends in a claim about the track's session and that condition supports
    none of them.
    """
    if refuses_recorded_target and sup.tmux.session_exists(session=session):
        recovery = _supervisor_herdr_stall.reconcile_and_alert(
            sup=sup,
            track=track,
            target=session,
            act=act,
            alert=act,
        )
        if recovery is not None:
            return recovery
    return _unavailable_target(sup=sup, track=track, session=session, act=act)


def _renumbered_herdr_coordinate(
    *, sup: Supervisor, track: registry.Track, session: str
) -> str | None:
    if not session.startswith(herdr_identity.HERDR_SCHEME):
        return None
    resolver = cast(
        Callable[..., str | None] | None,
        getattr(sup.tmux, "renumbered_herdr_coordinate", None),
    )
    if resolver is None:
        return None
    return resolver(
        session=session,
        observed_session_identity=track.observed_session_identity,
        starttime_of=sup.starttime_of,
    )


def _resolve_herdr_target(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> tuple[registry.Track, str, str | None, bool]:
    """Resolve an identity-bound Herdr target before trusting its positional id."""
    current = _renumbered_herdr_coordinate(sup=sup, track=track, session=session)
    refuses_recorded_target = session.startswith(
        herdr_identity.HERDR_SCHEME
    ) and _carries_claude_identity(track=track)
    relaunched = (
        _supervisor_herdr_moved.relaunched_identity(sup=sup, track=track, session=session)
        or _supervisor_herdr_moved.codex_successor_identity(
            sup=sup, track=track, session=session, act=act
        )
        if current is None and refuses_recorded_target
        else None
    )
    if relaunched is not None:
        if act:
            _ = registry.record_observed_session_identity(
                repo=track.repo,
                topic=track.topic,
                session_identity=relaunched,
                store_path=sup.store_path,
            )
        return replace(track, observed_session_identity=relaunched), session, session, False
    if current is None:
        return track, session, None, refuses_recorded_target
    if current == session:
        return track, session, session, False
    if act and not registry.repoint_tmux(
        repo=track.repo,
        topic=track.topic,
        new_tmux=current,
        store_path=sup.store_path,
    ):
        return track, session, None, True
    if act:
        old_pane = cast(
            herdr_identity.HerdrPaneTarget,
            herdr_identity.decode_target(value=session).herdr,
        )
        new_pane = cast(
            herdr_identity.HerdrPaneTarget,
            herdr_identity.decode_target(value=current).herdr,
        )
        sup.log(
            message=(
                "re-keyed renumbered herdr pane "
                f"{old_pane.pane_id} -> {new_pane.pane_id} "
                f"for {track.repo}::{track.topic}"
            )
        )
    return replace(track, tmux=current), current, current, False


def _carries_claude_identity(*, track: registry.Track) -> bool:
    return (track.observed_session_identity or "").startswith("claude:")


def resolve_evaluate_target(
    *, sup: Supervisor, track: registry.Track, act: bool
) -> RowView | EvaluateTarget:
    if track.is_unassigned:
        return RowView(topic=track.topic, repo=track.repo, tmux=None, ctx=None, status="unassigned")

    session = _supervisor_launch.session_of(sup=sup, track=track)
    track, session, target, refuses_recorded_target = _resolve_herdr_target(
        sup=sup,
        track=track,
        session=session,
        act=act,
    )
    unidentified = _supervisor_unidentified_codex.preflight_unidentified(
        sup=sup,
        track=track,
        target=target or session,
        act=act,
    )
    if unidentified is not None:
        return unidentified

    # A recorded process generation is authoritative for Herdr. Positional pane ids
    # can be reused, so existence of the old id cannot prove that it still names this
    # track. If the generation scan found no unique match, refuse the pane even when
    # the old id remains present. Rows without a recorded Claude identity retain the
    # legacy existence path because there is no process generation available to
    # validate; `_unproven_herdr_target` then requires the pane to name the topic.
    if target is None and (refuses_recorded_target or not sup.tmux.session_exists(session=session)):
        # A row assigned before the herdr cutover still names a retired TMUX session,
        # so the coordinate is dead while the track is not. Rebind it to the pane whose
        # resolved Codex identity is the one this row recorded, before concluding
        # anything about the track's session.
        rebound = _supervisor_codex_rebind.rebound_codex_coordinate(
            sup=sup, track=track, session=session, act=act
        )
        if rebound is None:
            ambiguous = _supervisor_codex_rebind.ambiguous_rebind_row(
                sup=sup, track=track, session=session, act=act
            )
            if ambiguous is not None:
                return ambiguous
            # The mapped TMUX session is gone — but the work may not be. A Claude
            # session for the same plan can keep running in a NON-tmux terminal (a bare
            # SSH shell), which the tmux-only daemon cannot capture, inject, or respawn.
            # Distinguish that live-but-unmanageable case from a genuinely gone track so
            # the operator is not falsely alarmed that finished-looking work was lost.
            return _unresolved_target(
                sup=sup,
                track=track,
                session=session,
                act=act,
                refuses_recorded_target=refuses_recorded_target,
            )
        # Carry the rebound coordinate into THIS tick rather than waiting for the next
        # one: a rebind that only rewrote the store would leave the track reading
        # `session-gone` for the rest of the tick that repaired it. Every gate below
        # still judges the new pane on its own evidence.
        track = replace(
            track,
            tmux=rebound.coordinate,
            observed_session_identity=rebound.identity,
        )
        session, target = rebound.coordinate, rebound.coordinate

    # Resolve the pane id ONCE and target every subsequent pane op by it (RB3).
    # A pane id is exact and never prefix/fnmatch-matched, so if the tracked
    # session dies mid-tick the ops fail-soft instead of a bare `-t <name>`
    # falling back to a live SIBLING session (e.g. dead `livespec--overseer`
    # resolving to live `livespec--overseer-rewrite`) and, worst case,
    # `respawn-pane -k` killing it. Stable across respawn.
    if target is None:
        target = sup.tmux.pane_id(session=session)
    if target is None:
        return _unavailable_target(sup=sup, track=track, session=session, act=act)

    return evaluate_managed_target(
        sup=sup,
        track=track,
        session=session,
        target=target,
        act=act,
    )
