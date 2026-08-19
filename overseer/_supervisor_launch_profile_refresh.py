"""Wrap-up-time launch-profile refresh for model-preserving restarts."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import _supervisor_launch
import claude_sessions
import registry
from _supervisor_launch_profile import (
    LaunchProfileProblem,
    read_launch_profile,
    rendered_statusline_model,
)
from _supervisor_launch_profile_sources import CodexProfileReaders, live_profile_sources

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "refresh_launch_profile_at_wrapup",
]


def _profile_sessions_dir(*, sup: Supervisor) -> str | os.PathLike[str]:
    if sup.sessions_dir is not None:
        return sup.sessions_dir
    return claude_sessions.default_sessions_dir()


def _codex_profile_readers(*, sup: Supervisor) -> CodexProfileReaders:
    return CodexProfileReaders(
        codex_home=sup.codex_home,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
    )


def _stored_model_profile(
    *,
    sup: Supervisor,
    track: registry.Track,
) -> dict[str, str | None] | None:
    if track.model_profile is not None:
        return track.model_profile
    for candidate in registry.read_valid_mapping(store_path=sup.store_path):
        if candidate.repo == track.repo and candidate.topic == track.topic:
            return candidate.model_profile
    return None


def refresh_launch_profile_at_wrapup(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    capture: str,
) -> None:
    session = _supervisor_launch.session_of(sup=sup, track=track)
    source = live_profile_sources(
        sessions_dir=_profile_sessions_dir(sup=sup),
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        ppid_of=sup.ppid_of,
        starttime_of=sup.starttime_of,
        codex_readers=_codex_profile_readers(sup=sup),
    ).get((session, track.topic))
    rendered = rendered_statusline_model(capture=capture)
    stored_profile = _stored_model_profile(sup=sup, track=track)
    if source is None:
        return
    profile = read_launch_profile(
        pid=source.pid,
        harness=source.harness,
        pane_pid=source.pane_pid,
        cmdline_of=sup.cmdline_of,
        environ_of=sup.environ_of,
        ppid_of=sup.ppid_of,
    )
    if isinstance(profile, LaunchProfileProblem):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=profile.message,
            condition="launch-profile-unreadable",
        )
        return
    if stored_profile is not None and profile["model"] != stored_profile["model"]:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=(
                "launch profile mismatch: "
                f"statusline rendered {rendered!r}, live model {profile['model']!r}, "
                f"stored model {stored_profile['model']!r}; persisting re-read argv/env"
            ),
            condition="launch-profile-mismatch",
        )
    if registry.record_model_profile(
        repo=track.repo,
        topic=track.topic,
        model_profile=profile,
        store_path=sup.store_path,
    ):
        sup.log(message=f"recorded launch profile for {track.repo}::{track.topic}")
