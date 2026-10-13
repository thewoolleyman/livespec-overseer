"""Initial target resolution for the supervisor evaluation cascade."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast

import _supervisor_herdr_recovery
import _supervisor_launch
import _supervisor_observe
import _supervisor_offer
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


def _unavailable_target(*, sup: Supervisor, track: registry.Track, session: str) -> RowView:
    recovery = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=sup,
        track=track,
        target=session,
        act=False,
    )
    if recovery is not None:
        return recovery
    return _supervisor_offer.no_managed_pane_row(sup=sup, track=track, session=session)


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


def resolve_evaluate_target(
    *, sup: Supervisor, track: registry.Track, act: bool
) -> RowView | EvaluateTarget:
    if track.is_unassigned:
        return RowView(topic=track.topic, repo=track.repo, tmux=None, ctx=None, status="unassigned")

    repo, topic = track.repo, track.topic
    session = _supervisor_launch.session_of(sup=sup, track=track)
    target: str | None = None

    if not sup.tmux.session_exists(session=session):
        current = _renumbered_herdr_coordinate(sup=sup, track=track, session=session)
        if current is not None and registry.repoint_tmux(
            repo=repo,
            topic=topic,
            new_tmux=current,
            store_path=sup.store_path,
        ):
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
                    f"{old_pane.pane_id} -> {new_pane.pane_id} for {repo}::{topic}"
                )
            )
            track = replace(track, tmux=current)
            session = current
            target = current
        if target is None:
            # The mapped TMUX session is gone — but the work may not be. A Claude
            # session for the same plan can keep running in a NON-tmux terminal (a bare
            # SSH shell), which the tmux-only daemon cannot capture, inject, or respawn.
            # Distinguish that live-but-unmanageable case from a genuinely gone track so
            # the operator is not falsely alarmed that finished-looking work was lost.
            return _unavailable_target(sup=sup, track=track, session=session)

    # Resolve the pane id ONCE and target every subsequent pane op by it (RB3).
    # A pane id is exact and never prefix/fnmatch-matched, so if the tracked
    # session dies mid-tick the ops fail-soft instead of a bare `-t <name>`
    # falling back to a live SIBLING session (e.g. dead `livespec--overseer`
    # resolving to live `livespec--overseer-rewrite`) and, worst case,
    # `respawn-pane -k` killing it. Stable across respawn.
    if target is None:
        target = sup.tmux.pane_id(session=session)
    if target is None:
        return _unavailable_target(sup=sup, track=track, session=session)

    recovery = _supervisor_herdr_recovery.reconcile_bare_shell(
        sup=sup,
        track=track,
        target=target,
        act=act,
    )
    if recovery is not None:
        return recovery

    # Identity gate (B3): the mapped session exists, but before reading its pane
    # for any ACT we confirm it is really OUR Claude in OUR repo — never
    # keystroke into a shell / wrong session / human split-pane.
    if not _supervisor_observe.pane_is_managed(
        sup=sup, target=target, repo=repo, topic=topic, session=session
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
        return _supervisor_offer.no_managed_pane_row(sup=sup, track=track, session=session)

    return EvaluateTarget(
        track=track,
        repo=repo,
        topic=topic,
        session=session,
        key=track_key(repo=repo, topic=topic),
        pane=target,
    )
