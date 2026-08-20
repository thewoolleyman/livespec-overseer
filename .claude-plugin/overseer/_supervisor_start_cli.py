"""Start-command launch outcome classification."""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
import signals
import tmuxio

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["launch_attempt_message"]


def launch_attempt_message(
    *, sup: Supervisor, io: tmuxio.PaneDriver, track: registry.Track, session: str
) -> str | None:
    if sup.do_launch(track=track, session=session, start=True):
        return f"started {track.repo}::{track.topic} in tmux session {session}"
    if not (
        io.session_exists(session=session)
        and signals.pane_is_claude(pane_current_command=io.pane_current_command(session=session))
    ):
        return None
    registry.set_resume_pending(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
    return (
        f"launched-unverified {track.repo}::{track.topic} in tmux session {session}; "
        "mapping upserted and resume retry pending"
    )
