"""Wrap-up-time launch-profile refresh for model-preserving restarts."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import _supervisor_launch
import claude_sessions
import registry
from _supervisor_codex_adoption import codex_host_readers
from _supervisor_launch_profile import (
    LaunchProfileProblem,
    apply_runtime_model,
    read_launch_profile,
    rendered_statusline_model,
)
from _supervisor_launch_profile_sources import live_profile_sources

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "refresh_launch_profile_at_wrapup",
]


def _profile_sessions_dir(*, sup: Supervisor) -> str | os.PathLike[str]:
    if sup.sessions_dir is not None:
        return sup.sessions_dir
    return claude_sessions.default_sessions_dir()


def _persisted_model_profile(
    *,
    sup: Supervisor,
    track: registry.Track,
) -> dict[str, str | None] | None:
    """The profile the PERSISTED row carries, independent of the in-memory Track."""
    for candidate in registry.read_valid_mapping(store_path=sup.store_path):
        if candidate.repo == track.repo and candidate.topic == track.topic:
            return candidate.model_profile
    return None


def _stored_model_profile(
    *,
    track: registry.Track,
    persisted_profile: dict[str, str | None] | None,
) -> dict[str, str | None] | None:
    if track.model_profile is not None:
        return track.model_profile
    return persisted_profile


def _with_statusline_baseline(
    *,
    profile: dict[str, str | None],
    stored_profile: dict[str, str | None] | None,
    persisted_profile: dict[str, str | None] | None,
    rendered: str | None,
) -> dict[str, str | None]:
    # At round open the pane's rendered model is authoritative: nothing has
    # been restarted yet, so whatever the session runs is what operator or
    # enforcement authority left it running. Re-baseline the statusline_model
    # from the live render so a wrong inherited baseline cannot veto restarts
    # forever. Fail-soft: an unreadable render keeps the stored value rather
    # than silently clearing it.
    if rendered is not None:
        return {**profile, "statusline_model": rendered}
    recorded = None if stored_profile is None else stored_profile.get("statusline_model")
    # REGRESSION GUARD: a write must never DROP a key the STORED ROW already carries.
    # `_stored_model_profile` prefers the in-memory Track whenever its profile is
    # non-None, and a reserved seat is BORN with a non-None but KEYLESS profile — so
    # `recorded` can be None while the persisted row holds a real baseline, and this
    # write would silently clear it. Guarding the key, not the VALUE, is deliberate:
    # a readable render still re-bases the value above, which is the round-open
    # behaviour and is untouched here.
    if recorded is None:
        recorded = None if persisted_profile is None else persisted_profile.get("statusline_model")
    if recorded is not None:
        return {**profile, "statusline_model": recorded}
    return profile


def _surface_statusline_rebaseline(
    *,
    sup: Supervisor,
    track: registry.Track,
    stored_profile: dict[str, str | None] | None,
    rendered: str | None,
) -> None:
    recorded = None if stored_profile is None else stored_profile.get("statusline_model")
    if rendered is None or recorded is None or rendered == recorded:
        return
    sup.log(
        message=(
            "statusline baseline re-based at round open for "
            f"{track.repo}::{track.topic}: {recorded!r} -> {rendered!r}"
        ),
    )


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
        codex_readers=codex_host_readers(sup=sup),
    ).get((session, track.topic))
    rendered = rendered_statusline_model(capture=capture)
    persisted_profile = _persisted_model_profile(sup=sup, track=track)
    stored_profile = _stored_model_profile(track=track, persisted_profile=persisted_profile)
    if source is None:
        return
    profile = apply_runtime_model(
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
    _surface_statusline_rebaseline(
        sup=sup,
        track=track,
        stored_profile=stored_profile,
        rendered=rendered,
    )
    profile = _with_statusline_baseline(
        profile=profile,
        stored_profile=stored_profile,
        persisted_profile=persisted_profile,
        rendered=rendered,
    )
    if registry.record_model_profile(
        repo=track.repo,
        topic=track.topic,
        model_profile=profile,
        store_path=sup.store_path,
    ):
        sup.log(message=f"recorded launch profile for {track.repo}::{track.topic}")
