"""Claude-specific post-respawn verification for supervisor restarts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["claude_respawn_verified"]


def _post_respawn_claude_process_live(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
) -> bool:
    for _ in range(_supervisor_launch.RESTART_POLL_MAX):
        sup.refresh_claude_status()
        if sup.claude_identity_by_session.get((session, track.topic)) is not None:
            return True
        sup.sleep(_supervisor_launch.RESTART_POLL_INTERVAL)
    return False


def claude_respawn_verified(*, sup: Supervisor, track: registry.Track, target: str) -> bool:
    if not _supervisor_launch.await_pane(sup=sup, target=target, is_ready=signals.pane_is_claude):
        registry.set_resume_pending(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=_supervisor_launch.session_of(sup=sup, track=track),
            pane=target,
            message="respawned pane never became Claude; will retry resume without respawn",
        )
        return False
    session = _supervisor_launch.session_of(sup=sup, track=track)
    if not _post_respawn_claude_process_live(sup=sup, track=track, session=session):
        registry.set_resume_pending(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="respawned pane has no live Claude process; keeping the ready declaration",
            condition="claude-post-respawn-live-missing",
        )
        return False
    return True
