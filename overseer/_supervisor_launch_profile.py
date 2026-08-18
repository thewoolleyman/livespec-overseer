"""Claude launch-profile planning for restart and reboot recovery."""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import registry

__all__: list[str] = [
    "CLAUDE_CONTROLLED_ENV",
    "ClaudeLaunchPlan",
    "LaunchProfileProblem",
    "claude_launch_plan",
]

CLAUDE_CONTROLLED_ENV = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_DISABLE_1M_CONTEXT",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
)


@dataclass(frozen=True, kw_only=True)
class ClaudeLaunchPlan:
    command: str
    env: Mapping[str, str | None]


@dataclass(frozen=True, kw_only=True)
class LaunchProfileProblem:
    message: str


def _scrubbed_env() -> dict[str, str | None]:
    return {name: None for name in CLAUDE_CONTROLLED_ENV}


def _bare_command(*, track: registry.Track) -> str:
    return f"claude --dangerously-skip-permissions -n {shlex.quote(track.topic)}"


def _problem(*, track: registry.Track, reason: str) -> LaunchProfileProblem:
    return LaunchProfileProblem(
        message=f"stale launch profile for {track.repo}::{track.topic}: {reason}"
    )


def _wrapper_problem(*, track: registry.Track, wrapper: str) -> LaunchProfileProblem | None:
    path = Path(wrapper)
    if path.is_file() and os.access(path, os.X_OK):
        return None
    return _problem(track=track, reason=f"wrapper {wrapper!r} does not exist or is not executable")


def claude_launch_plan(*, track: registry.Track) -> ClaudeLaunchPlan | LaunchProfileProblem:
    profile = track.model_profile
    if profile is None:
        return ClaudeLaunchPlan(command=_bare_command(track=track), env=_scrubbed_env())
    if profile["harness"] != "claude":
        return _problem(
            track=track,
            reason=f"harness {profile['harness']!r} cannot relaunch a Claude track",
        )
    model = cast(str, profile["model"])
    env = _scrubbed_env()
    wrapper = profile["wrapper"]
    if wrapper is None:
        return ClaudeLaunchPlan(
            command=(
                f"claude --model {shlex.quote(model)} "
                f"--dangerously-skip-permissions -n {shlex.quote(track.topic)}"
            ),
            env=MappingProxyType(env),
        )
    wrapper_problem = _wrapper_problem(track=track, wrapper=wrapper)
    if wrapper_problem is not None:
        return wrapper_problem
    env["ANTHROPIC_MODEL"] = model
    return ClaudeLaunchPlan(
        command=(
            f"{shlex.quote(wrapper)} "
            f"--dangerously-skip-permissions -n {shlex.quote(track.topic)}"
        ),
        env=MappingProxyType(env),
    )
