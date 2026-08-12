"""Report-only attention for a fresh session that never began work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_liveness
import _supervisor_observe
import registry
import signals
from _supervisor_config import POST_RESPAWN_NEVER_WORKED_AFTER
from _supervisor_records import Observation
from _supervisor_resume_retry import resume_retry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["post_respawn_decision"]


@dataclass(frozen=True, kw_only=True)
class RestartNeverWorked:
    ctx: int
    resume: str


def _post_respawn(*, sup: Supervisor, track: registry.Track) -> RestartNeverWorked | None:
    recorded = registry.read_post_respawn(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    if recorded is None:
        return None
    ctx, resume = recorded
    return RestartNeverWorked(ctx=ctx, resume=resume)


def _restart_never_worked(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    session: str,
    pane: str,
    act: bool,
) -> tuple[RowView, set[str]] | None:
    """Return the report-only post-respawn attention row when the 60s floor is met."""
    recorded = _post_respawn(sup=sup, track=track)
    expected_resume = None if recorded is None else recorded.resume
    no_context_consumed = (
        recorded is not None and obs.eff_ctx is not None and obs.eff_ctx == recorded.ctx
    )
    composer_matches = (
        expected_resume is not None
        and signals.input_box_text(capture_text=obs.capture) == expected_resume
    )
    _supervisor_observe.advance_condition(
        episode=obs.istate.restart_never_worked_episode,
        condition_now=no_context_consumed and composer_matches,
        now=sup.now(),
    )
    since = obs.istate.restart_never_worked_episode.since
    age = 0.0 if since is None else max(0.0, sup.now() - since)
    if since is None or age < POST_RESPAWN_NEVER_WORKED_AFTER:
        return None

    condition = "restart-never-worked"
    note = (
        f"{_supervisor_liveness.age_label(seconds=age)}: "
        "fresh session has not consumed context and still holds the resume text"
    )
    if act:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=pane,
            message="fresh session has not begun work after restart — inspect that pane",
            condition=condition,
        )
    return (
        RowView(
            topic=track.topic,
            repo=track.repo,
            tmux=session,
            ctx=obs.eff_ctx,
            status=condition,
            note=note,
            runtime=obs.runtime,
        ),
        {condition},
    )


def post_respawn_decision(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    act: bool,
    session: str,
    target: str,
) -> RowView | None:
    """Handle post-respawn recovery/reporting before the normal cascade."""
    retry = resume_retry(sup=sup, track=track, obs=obs, act=act, session=session, target=target)
    if retry is not None:
        return retry
    decision = _restart_never_worked(
        sup=sup,
        track=track,
        obs=obs,
        session=session,
        pane=target,
        act=act,
    )
    if decision is None:
        return None
    view, active_conditions = decision
    if act:
        _supervisor_liveness.clear_alert_conditions(
            sup=sup,
            repo=track.repo,
            topic=track.topic,
            conditions=frozenset(active_conditions),
        )
    return view
