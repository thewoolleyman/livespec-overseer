"""Start-command launch outcome classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import tmuxio

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["StartLaunchMessage", "launch_attempt_message"]


@dataclass(frozen=True, kw_only=True)
class StartLaunchMessage:
    message: str | None
    reason: str | None = None


def launch_attempt_message(
    *, sup: Supervisor, io: tmuxio.PaneDriver, track: registry.Track, session: str
) -> StartLaunchMessage:
    del io
    result = sup.do_launch_result(track=track, session=session, start=True)
    if result.launched:
        if result.reason == "resume_submit_unverified":
            registry.set_resume_pending(
                repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path
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
    return StartLaunchMessage(message=None, reason=result.reason or "claude_launch_failed")
