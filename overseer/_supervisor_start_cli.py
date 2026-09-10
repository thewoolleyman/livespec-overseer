"""Start-command launch outcome classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_recovery
import registry
import tmuxio
from _supervisor_dead_track import LaunchableRuntime

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["StartLaunchMessage", "launch_attempt_message"]


@dataclass(frozen=True, kw_only=True)
class StartLaunchMessage:
    message: str | None
    reason: str | None = None


def launch_attempt_message(
    *,
    sup: Supervisor,
    io: tmuxio.PaneDriver,
    track: registry.Track,
    session: str,
    runtime: LaunchableRuntime,
) -> StartLaunchMessage:
    """Launch the track as its ESTABLISHED runtime and describe the outcome.

    ``runtime`` comes from :func:`_supervisor_dead_track.classify_dead_track`, which the
    caller ran before creating any session, so this never enters the Claude path for a
    track with a proven Codex identity. The ``resume_submit_unverified`` retry below is
    Claude-only by construction: ``codex resume`` carries its kick as an argument and
    auto-submits it, so there is no separate paste that could strand.
    """
    del io
    result = _supervisor_recovery.dead_track_launch_result(
        sup=sup, track=track, session=session, runtime=runtime, start=True
    )
    if result.launched:
        if result.reason == "resume_submit_unverified":
            sup.refresh_claude_status()
            registry.set_resume_pending(
                repo=track.repo,
                topic=track.topic,
                session_identity=sup.claude_identity_by_session.get((session, track.topic)),
                stamp_path=sup.stamp_path,
            )
            return StartLaunchMessage(
                message=(
                    f"launched-unverified {track.repo}::{track.topic} in tmux session {session}; "
                    "mapping upserted and resume retry pending"
                )
            )
        return StartLaunchMessage(
            message=f"started {track.repo}::{track.topic} in tmux session {session}"
        )
    return StartLaunchMessage(message=None, reason=result.reason or "launch_failed")
