"""_supervisor_pair — supervisor pair-member evaluation and pair-stall ladder.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the second per-tick pass for the attended supervisor beside a
worker track, plus the Lane D pair-stall detector that runs only after both pair
members have been evaluated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_evaluate
import _supervisor_offer
import registry
import signals
from _supervisor_pair_stall import evaluate_pair_stall
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["evaluate_pair_stall", "evaluate_supervisor_pair"]


def evaluate_supervisor_pair(
    *, sup: Supervisor, track: registry.Track, act: bool
) -> RowView | None:
    """Evaluate the attended supervisor pair member independently of the worker.

    The worker's own cascade must not decide whether its pair is visible. A running
    supervisor, or one that vanished during an open wind-down round, is projected as its
    own supervised row. A missing supervisor with no open round is surfaced through the
    ordinary supervision-offer machinery instead.
    """
    if track.is_unassigned:
        return None
    repo, topic = track.repo, track.topic
    session = _supervisor_offer.supervisor_session_of(sup=sup, track=track)
    entity_topic = signals.supervisor_entity_topic(topic=topic)
    stamp = registry.read_injection_stamp(repo=repo, topic=entity_topic, stamp_path=sup.stamp_path)
    if not _supervisor_offer.supervisor_running(sup=sup, session=session, repo=repo):
        _supervisor_offer.surface_supervision_offer(sup=sup, track=track, act=act)
        if stamp is None:
            return None
        if act:
            sup.alert(
                repo=repo,
                topic=entity_topic,
                session=session if sup.tmux.session_exists(session=session) else None,
                pane=sup.tmux.pane_id(session=session),
                message="supervisor vanished during an open wind-down round",
                condition="supervisor-gone-mid-round",
            )
        return RowView(
            topic=entity_topic,
            repo=repo,
            tmux=None,
            ctx=None,
            status="session-gone",
            note="supervisor vanished during an open wind-down round",
        )
    _supervisor_offer.surface_supervision_offer(sup=sup, track=track, act=act)
    # The pair shares ONE epic and one stream (spec section "the supervisor pair member"),
    # so the entity track carries the worker's. Its own resume prompt is DERIVED from the
    # reserved entity topic rather than stored here, which is why no `resume` is set.
    epic = track.epic
    if not registry.epic_is_resolved(epic=epic) or epic is None:
        return None
    supervisor_track = registry.SupervisorSeat(
        topic=entity_topic,
        repo=repo,
        tmux=session,
        epic=epic,
        supervised_topic=topic,
    )
    return _supervisor_evaluate.evaluate(sup=sup, track=supervisor_track, act=act)
