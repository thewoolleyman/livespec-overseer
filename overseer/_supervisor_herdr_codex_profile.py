"""Capture the launch profile when a Herdr pane changes from Claude to Codex."""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
from _supervisor_launch_profile import complete_launch_profile, read_launch_profile
from _supervisor_launch_profile_sources import LaunchProfileSource, codex_model_source
from _supervisor_statusline_model import rendered_statusline_model

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["recapture_codex_successor_profile"]


def recapture_codex_successor_profile(
    *, sup: Supervisor, track: registry.Track, session: str
) -> bool:
    """Persist the complete profile from the proven Codex carrier replacing Claude."""
    live = sup.live_codex[(session, track.topic)]
    source = LaunchProfileSource(
        pid=live.pid,
        harness="codex",
        pane_pid=next(
            (
                pid
                for pid, coordinate in sup.tmux.pane_pid_sessions().items()
                if coordinate == session
            ),
            None,
        ),
        session_id=live.session_id,
        cwd=live.cwd,
    )
    profile = complete_launch_profile(
        profile=read_launch_profile(
            pid=source.pid,
            harness=source.harness,
            pane_pid=source.pane_pid,
            cmdline_of=sup.cmdline_of,
            environ_of=sup.environ_of,
            ppid_of=sup.ppid_of,
        ),
        harness=source.harness,
        pid=source.pid,
        runtime_model_of=sup.runtime_model_of,
        codex_identity=codex_model_source(
            source=source,
            environ_of=sup.environ_of,
            codex_home=sup.codex_home,
        ),
    )
    if not isinstance(profile, dict):
        return False
    return registry.record_model_profile(
        repo=track.repo,
        topic=track.topic,
        model_profile={
            **profile,
            "statusline_model": rendered_statusline_model(
                capture=sup.tmux.capture_pane(session=session)
            ),
        },
        store_path=sup.store_path,
    )
