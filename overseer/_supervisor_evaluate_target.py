"""Initial target resolution for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

import _supervisor_codex_misnamed
import _supervisor_codex_rebind
import _supervisor_discovery
import _supervisor_herdr_moved
import _supervisor_herdr_stall
import _supervisor_launch
import _supervisor_observe
import herdr_identity
import registry
from _supervisor_config import track_key
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["EvaluateTarget", "resolve_evaluate_target"]


@dataclass(frozen=True, kw_only=True)
class EvaluateTarget:
    track: registry.Track
    repo: str
    topic: str
    session: str
    key: tuple[str, str]
    pane: str


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

    Before any of that, the unidentifiable-Codex condition is ruled out, because every
    route below ends in a claim about the track's session and that condition supports
    none of them: a live Codex pane in this repo whose identity could not be resolved
    means the daemon cannot SAY, which is the opposite of `session-gone`.
    """
    if _supervisor_codex_rebind.unidentified_codex_pane(sup=sup, track=track):
        return RowView(
            topic=track.topic,
            repo=track.repo,
            tmux=None,
            ctx=None,
            status="codex-unidentified",
            note=_supervisor_codex_rebind.UNIDENTIFIED_NOTE,
        )
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


def _resolve_herdr_target(
    *, sup: Supervisor, track: registry.Track, session: str, act: bool
) -> tuple[registry.Track, str, str | None, bool]:
    """Resolve an identity-bound Herdr target before trusting its positional id."""
    current = _supervisor_herdr_moved.renumbered_coordinate(sup=sup, track=track, session=session)
    refuses_recorded_target = session.startswith(
        herdr_identity.HERDR_SCHEME
    ) and _carries_claude_identity(track=track)
    relaunched = (
        _supervisor_herdr_moved.relaunched_identity(sup=sup, track=track, session=session)
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


def _unproven_herdr_target(
    *, sup: Supervisor, track: registry.Track, session: str, target: str
) -> bool:
    """Whether a Herdr row without a Claude process identity fails to name its topic.

    Positional Herdr ids are reused, and the shared topic-name check passes an empty
    name set so a transient registry miss cannot flap a tmux track. Only a recorded
    Claude identity carries a process generation the re-key scan can validate; any
    other row keeps the existence path, where that pass would let a reused id route
    this track to a foreign pane. Such a row must instead show a live Claude named for
    its topic, or be a live Codex track, in that exact pane.
    """
    if not session.startswith(herdr_identity.HERDR_SCHEME):
        return False
    if _carries_claude_identity(track=track):
        return False
    if track.topic in sup.claude_names_by_session.get(session, set()):
        return False
    return not _supervisor_observe.is_codex_track(
        sup=sup, session=session, repo=track.repo, topic=track.topic, target=target
    )


def resolve_evaluate_target(
    *, sup: Supervisor, track: registry.Track, act: bool
) -> RowView | EvaluateTarget:
    if track.is_unassigned:
        return RowView(topic=track.topic, repo=track.repo, tmux=None, ctx=None, status="unassigned")

    repo, topic = track.repo, track.topic
    session = _supervisor_launch.session_of(sup=sup, track=track)
    # Re-read the registry before the Herdr relaunch path records an identity from it.
    _supervisor_discovery.refresh_claude_track(sup=sup, session=session, topic=track.topic)
    resolved_from = session
    track, session, target, refuses_recorded_target = _resolve_herdr_target(
        sup=sup,
        track=track,
        session=session,
        act=act,
    )
    if session != resolved_from:
        _supervisor_discovery.refresh_claude_track(sup=sup, session=session, topic=track.topic)

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
        track, session, target = replace(track, tmux=rebound), rebound, rebound

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

    recovery = _supervisor_herdr_stall.reconcile_and_alert(
        sup=sup,
        track=track,
        target=target,
        act=act,
        alert=act,
    )
    if recovery is not None:
        return recovery

    # Identity gate (B3): the mapped session exists, but before reading its pane
    # for any ACT we confirm it is really OUR Claude in OUR repo — never
    # keystroke into a shell / wrong session / human split-pane.
    if _unproven_herdr_target(sup=sup, track=track, session=session, target=target) or not (
        _supervisor_observe.pane_is_managed(
            sup=sup, target=target, repo=repo, topic=topic, session=session
        )
    ):
        # The gate stays exactly what it was — an ACT guard (never keystroke into a
        # pane not proven ours). What changed is that its answer is no longer a row
        # STATUS of its own. Whether the pane is a bare shell (our session exited) or
        # something foreign, the fact for the operator is identical and simple: this
        # track's session is NOT IN THIS TMUX. It was assigned to something once, so
        # it is `session-gone` — never `unassigned`, which is reserved for a plan
        # whose session we have NEVER seen (maintainer-declared 2026-07-17: "KEEP
        # session-gone if you've ever seen the session, only use unassigned if you've
        # never seen it"). The MAPPING ROW is precisely that memory of having seen it,
        # which is why it is kept rather than pruned.
        #
        # `not-claude` is DELETED (maintainer-declared 2026-07-17: "What the hell is
        # not-claude?"). It was this gate's return value leaking into the UI — it named
        # a check's output, not anything an operator needs — and it made a bare
        # terminal (`livespec1`) look like a tracked pane while no OTHER bare terminal
        # appears at all. The daemon lists PLANS, not panes: a tmux name reaches the
        # table only as a mapping's column value, and `_no_managed_pane_row` already
        # reports `tmux=None` so no dead terminal is named.
        return _supervisor_codex_misnamed.gone_row(sup=sup, track=track, session=session, act=act)

    return EvaluateTarget(
        track=track,
        repo=repo,
        topic=topic,
        session=session,
        key=track_key(repo=repo, topic=topic),
        pane=target,
    )
