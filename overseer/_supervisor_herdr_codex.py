"""Ready-round binding for a fresh Codex replacement in a Herdr pane."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _herdr_replacement_authorization
import _supervisor_herdr_replacement
import _supervisor_launch
import registry
from _supervisor_launch_profile import CodexLaunchPlan, codex_fresh_launch_plan
from _supervisor_profile_self_heal import heal_cross_runtime_profile
from _supervisor_prompts import resume_for_track
from _supervisor_statusline_model import (
    restart_blocked_by_statusline_mismatch as statusline_mismatch,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["begin_codex_replacement"]


def _refuse(
    *, sup: Supervisor, track: registry.Track, target: str, message: str, condition: str
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        pane=target,
        message=message,
        condition=condition,
    )


def begin_codex_replacement(
    *, sup: Supervisor, track: registry.Track, target: str
) -> _supervisor_herdr_replacement.ReplacementFailure | None:
    """Freeze the live Codex process, rollout, profile, and continuation before signal."""
    session = _supervisor_launch.session_of(sup=sup, track=track)
    live = sup.live_codex.get((session, track.topic))
    prior_rollout = (
        None
        if live is None
        else _supervisor_launch.canonical_codex_session_id(value=live.session_id)
    )
    starttime = None if live is None else sup.starttime_of(pid=live.pid)
    if live is None or prior_rollout is None or starttime is None:
        _refuse(
            sup=sup,
            track=track,
            target=target,
            message="Codex process generation or rollout vanished before Herdr replacement",
            condition="codex-session-vanished-before-restart",
        )
        return None
    resume = resume_for_track(track=track)
    if resume is None:
        _refuse(
            sup=sup,
            track=track,
            target=target,
            message="ready cannot replace Codex: no plan epic recorded",
            condition="restart-plan-epic-missing",
        )
        return None
    launch = codex_fresh_launch_plan(track=track, daemon_restart=True)
    if not isinstance(launch, CodexLaunchPlan):
        if heal_cross_runtime_profile(sup=sup, track=track, session=session, target=target):
            return None
        _refuse(
            sup=sup,
            track=track,
            target=target,
            message=f"{launch.message}; keeping the ready declaration so it retries",
            condition="stale-launch-profile",
        )
        return None
    if statusline_mismatch(sup=sup, track=track, target=target, session=session):
        return None
    return _supervisor_herdr_replacement.begin_herdr_replacement(
        sup=sup,
        track=track,
        target=target,
        launch=launch,
        binding=_herdr_replacement_authorization.ReplacementBinding(
            runtime="codex",
            predecessor_identity=f"codex:{live.pid}:{starttime}:{track.topic}",
            predecessor_rollout=prior_rollout,
            resume=resume,
        ),
    )
