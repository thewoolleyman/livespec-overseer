"""_supervisor_pair — supervisor pair-member evaluation and pair-stall ladder.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the second per-tick pass for the attended supervisor beside a
worker track, plus the Lane D pair-stall detector that runs only after both pair
members have been evaluated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_evaluate
import _supervisor_launch
import _supervisor_observe
import _supervisor_offer
import _supervisor_prompts
import registry
import signals
from _supervisor_config import PAIR_STALL_AFTER, track_key
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import PairStallState

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
    supervisor_track = registry.Track(
        topic=entity_topic,
        repo=repo,
        tmux=session,
        handoff=str(_supervisor_prompts.supervisor_handoff_path(repo=repo, topic=topic)),
        resume=_supervisor_prompts.supervisor_resume(repo=repo, topic=topic),
    )
    return _supervisor_evaluate.evaluate(sup=sup, track=supervisor_track, act=act)


def evaluate_pair_stall(
    *,
    sup: Supervisor,
    track: registry.Track,
    worker_view: RowView,
    supervisor_view: RowView,
    act: bool,
) -> None:
    """Advance the pair-stall episode and act/escalate when its floor is reached."""
    if not act:
        return
    key = track_key(repo=track.repo, topic=track.topic)
    state = sup.pair_stalls.setdefault(key, _new_pair_state())
    now = sup.now()
    if worker_view.progress_now:
        state.consecutive_nudged_episodes = 0
    stalled_now = _pair_stalled_now(worker_view=worker_view, supervisor_view=supervisor_view)
    if not stalled_now:
        _clear_pair_episode(
            sup=sup,
            track=track,
            state=state,
            now=now,
            worker_progress=worker_view.progress_now,
        )
        return
    _advance_pair_episode(state=state, now=now)
    state.unstalled_since = None
    if state.since is None or (now - state.since) < PAIR_STALL_AFTER:
        return
    if _nudge_failed_long_enough(state=state, now=now) or (
        state.consecutive_nudged_episodes >= 1 and not state.nudged_this_episode
    ):
        _alert_pair_stalled(
            sup=sup,
            track=track,
            worker_view=worker_view,
            supervisor_view=supervisor_view,
        )
        return
    if not state.nudged_this_episode and _try_pair_nudge(
        sup=sup,
        track=track,
        worker_view=worker_view,
        supervisor_view=supervisor_view,
        stalled_seconds=now - state.since,
    ):
        state.nudged_this_episode = True
        state.last_nudged_at = now
        state.consecutive_nudged_episodes += 1


def _new_pair_state() -> PairStallState:
    from _supervisor_records import PairStallState

    return PairStallState()


def _pair_stalled_now(*, worker_view: RowView, supervisor_view: RowView) -> bool:
    return not (
        worker_view.progress_now
        or supervisor_view.progress_now
        or worker_view.human_wait
        or supervisor_view.human_wait
    )


def _advance_pair_episode(*, state: PairStallState, now: float) -> None:
    if state.since is None:
        if state.unstalled_since is not None and (now - state.unstalled_since) >= PAIR_STALL_AFTER:
            state.since = state.unstalled_since
        else:
            state.since = now
        state.nudged_this_episode = False
        state.last_nudged_at = None
    state.last_seen = now


def _clear_pair_episode(
    *,
    sup: Supervisor,
    track: registry.Track,
    state: PairStallState,
    now: float,
    worker_progress: bool,
) -> None:
    state.since = None
    state.last_seen = None
    state.nudged_this_episode = False
    state.last_nudged_at = None
    if worker_progress:
        state.unstalled_since = now
        state.consecutive_nudged_episodes = 0
    _ = sup.alerted.pop(
        (
            *track_key(repo=track.repo, topic=signals.supervisor_entity_topic(topic=track.topic)),
            "pair-stalled",
        ),
        None,
    )


def _nudge_failed_long_enough(*, state: PairStallState, now: float) -> bool:
    return state.last_nudged_at is not None and (now - state.last_nudged_at) >= PAIR_STALL_AFTER


def _try_pair_nudge(
    *,
    sup: Supervisor,
    track: registry.Track,
    worker_view: RowView,
    supervisor_view: RowView,
    stalled_seconds: float,
) -> bool:
    target = _pair_nudge_target(sup=sup, track=track, supervisor_view=supervisor_view)
    if target is None or not _pair_nudge_input_ready(
        sup=sup, track=track, supervisor_view=supervisor_view, target=target
    ):
        return False
    text = _supervisor_prompts.pair_stall_nudge_message(
        repo=track.repo,
        topic=track.topic,
        worker_session=worker_view.tmux or "unknown",
        worker_pane=sup.tmux.pane_id(session=worker_view.tmux) if worker_view.tmux else None,
        stalled_seconds=stalled_seconds,
    )
    return _supervisor_launch.submit_prompt(sup=sup, target=target, text=text)


def _pair_nudge_target(
    *, sup: Supervisor, track: registry.Track, supervisor_view: RowView
) -> str | None:
    if not _pair_nudge_allowed_by_rows(supervisor_view=supervisor_view):
        return None
    session = supervisor_view.tmux or ""
    target = sup.tmux.pane_id(session=session)
    return (
        target
        if target is not None
        and _supervisor_observe.pane_is_managed(
            sup=sup, target=target, repo=track.repo, topic=supervisor_view.topic, session=session
        )
        else None
    )


def _pair_nudge_input_ready(
    *, sup: Supervisor, track: registry.Track, supervisor_view: RowView, target: str
) -> bool:
    capture = sup.tmux.capture_pane(session=target)
    return (
        not signals.is_structured_gate(capture_text=capture)
        and signals.input_box_ready(capture_text=capture)
        and _supervisor_launch.pane_settled(sup=sup, target=target)
        and _supervisor_observe.pane_is_managed(
            sup=sup,
            target=target,
            repo=track.repo,
            topic=supervisor_view.topic,
            session=supervisor_view.tmux,
        )
    )


def _pair_nudge_allowed_by_rows(*, supervisor_view: RowView) -> bool:
    return (
        supervisor_view.runtime == "claude"
        and not supervisor_view.human_wait
        and not supervisor_view.round_open
        and not supervisor_view.acked
    )


def _alert_pair_stalled(
    *, sup: Supervisor, track: registry.Track, worker_view: RowView, supervisor_view: RowView
) -> None:
    sup.alert(
        repo=track.repo,
        topic=supervisor_view.topic,
        session=supervisor_view.tmux,
        pane=sup.tmux.pane_id(session=supervisor_view.tmux) if supervisor_view.tmux else None,
        message=(
            "PAIR STALLED — autonomous supervisor nudge already failed; "
            f"supervisor tmux session '{supervisor_view.tmux}' pane "
            f"{sup.tmux.pane_id(session=supervisor_view.tmux) if supervisor_view.tmux else None}; "
            f"worker tmux session '{worker_view.tmux}' pane "
            f"{sup.tmux.pane_id(session=worker_view.tmux) if worker_view.tmux else None}"
        ),
        condition="pair-stalled",
    )
