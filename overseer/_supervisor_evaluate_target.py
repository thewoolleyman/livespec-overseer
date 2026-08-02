"""Initial target resolution for the supervisor evaluation cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_observe
import _supervisor_offer
import registry
from _supervisor_config import track_key
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["EvaluateTarget", "resolve_evaluate_target"]


@dataclass(frozen=True, kw_only=True)
class EvaluateTarget:
    repo: str
    topic: str
    session: str
    key: tuple[str, str]
    pane: str


def resolve_evaluate_target(*, sup: Supervisor, track: registry.Track) -> RowView | EvaluateTarget:
    if track.is_unassigned:
        return RowView(topic=track.topic, repo=track.repo, tmux=None, ctx=None, status="unassigned")

    repo, topic = track.repo, track.topic
    session = _supervisor_launch.session_of(sup=sup, track=track)

    if not sup.tmux.session_exists(session=session):
        # The mapped TMUX session is gone — but the work may not be. A Claude
        # session for the same plan can keep running in a NON-tmux terminal (a bare
        # SSH shell), which the tmux-only daemon cannot capture, inject, or respawn.
        # Distinguish that live-but-unmanageable case from a genuinely gone track so
        # the operator is not falsely alarmed that finished-looking work was lost.
        return _supervisor_offer.no_managed_pane_row(sup=sup, track=track, session=session)

    # Resolve the pane id ONCE and target every subsequent pane op by it (RB3).
    # A pane id is exact and never prefix/fnmatch-matched, so if the tracked
    # session dies mid-tick the ops fail-soft instead of a bare `-t <name>`
    # falling back to a live SIBLING session (e.g. dead `livespec--overseer`
    # resolving to live `livespec--overseer-rewrite`) and, worst case,
    # `respawn-pane -k` killing it. Stable across respawn.
    target = sup.tmux.pane_id(session=session)
    if target is None:
        return _supervisor_offer.no_managed_pane_row(sup=sup, track=track, session=session)

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
        repo=repo,
        topic=topic,
        session=session,
        key=track_key(repo=repo, topic=topic),
        pane=target,
    )
