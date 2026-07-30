"""_supervisor_pair — supervisor pair-member evaluation for each worker track.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the second per-tick pass for the attended supervisor beside a
worker track. The worker cascade stays in :mod:`_supervisor_evaluate`; this pass runs
independently so a busy, blocked, warned, or dangerous worker cannot hide its
supervisor's own state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_evaluate
import _supervisor_offer
import _supervisor_prompts
import registry
import signals
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["evaluate_supervisor_pair"]


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
    supervisor_track = registry.Track(
        topic=entity_topic,
        repo=repo,
        tmux=session,
        handoff=str(_supervisor_prompts.supervisor_handoff_path(repo=repo, topic=topic)),
        resume=_supervisor_prompts.supervisor_resume(repo=repo, topic=topic),
    )
    return _supervisor_evaluate.evaluate(sup=sup, track=supervisor_track, act=act)
