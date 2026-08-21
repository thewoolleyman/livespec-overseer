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
from _supervisor_launch_profile_capture import LaunchProfileProblem, read_launch_profile
from _supervisor_statusline_model import rendered_statusline_model

__all__: list[str] = [
    "CLAUDE_CONTROLLED_ENV",
    "DEFAULT_START_MODEL",
    "ClaudeLaunchPlan",
    "CodexLaunchPlan",
    "LaunchProfileProblem",
    "claude_launch_plan",
    "codex_launch_plan",
    "read_launch_profile",
    "rendered_statusline_model",
]

CLAUDE_CONTROLLED_ENV = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_DISABLE_1M_CONTEXT",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
)

# The model a track the overseer STARTS is launched under, so its argv carries a token the
# capture can read and the track is capturable from birth. Deliberately a CONSTANT rather
# than a read of the runtime's own configured default: that default is not stable (measured
# moving twice inside one day on 2026-08-19/20), so reading it would make the launch token
# arbitrary at exactly the moment it needs to be deterministic. The bracketed context-variant
# alias is accepted by the model flag and MUST be kept — dropping it silently relaunches the
# fleet on a smaller context window, which is the harm this whole section exists to close.
DEFAULT_START_MODEL = "opus[1m]"


@dataclass(frozen=True, kw_only=True)
class ClaudeLaunchPlan:
    command: str
    env: Mapping[str, str | None]


@dataclass(frozen=True, kw_only=True)
class CodexLaunchPlan:
    command: str
    env: Mapping[str, str | None] | None


def _scrubbed_env() -> dict[str, str | None]:
    return {name: None for name in CLAUDE_CONTROLLED_ENV}


def _claude_command(*, topic: str, model: str | None) -> str:
    """The Claude launch command, with an explicit model only when one is given."""
    model_arg = "" if model is None else f"--model {shlex.quote(model)} "
    return f"claude {model_arg}--dangerously-skip-permissions -n {shlex.quote(topic)}"


def _problem(*, track: registry.Track, reason: str) -> LaunchProfileProblem:
    return LaunchProfileProblem(
        message=f"stale launch profile for {track.repo}::{track.topic}: {reason}"
    )


def _wrapper_problem(*, track: registry.Track, wrapper: str) -> LaunchProfileProblem | None:
    path = Path(wrapper)
    if path.is_file() and os.access(path, os.X_OK):
        return None
    return _problem(track=track, reason=f"wrapper {wrapper!r} does not exist or is not executable")


def claude_launch_plan(
    *, track: registry.Track, start: bool = False
) -> ClaudeLaunchPlan | LaunchProfileProblem:
    """Plan a Claude launch. ``start`` marks a brand-new track rather than a relaunch.

    The two differ because the specification governs them differently. A row with no
    recorded profile MUST "continue to relaunch exactly as it does today", so both
    relaunch paths keep the bare command byte-for-byte. A START is not a relaunch and is
    not covered by that clause, so it may name a model — which is what makes the track
    capturable, ends the launched-bare-relaunched-bare loop, and leaves fail-soft intact.
    """
    profile = track.model_profile
    if profile is None:
        return ClaudeLaunchPlan(
            command=_claude_command(
                topic=track.topic, model=DEFAULT_START_MODEL if start else None
            ),
            env=_scrubbed_env(),
        )
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
            command=_claude_command(topic=track.topic, model=model),
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


def _bare_codex_command(*, session_id: str, resume: str) -> str:
    return (
        "codex resume --dangerously-bypass-approvals-and-sandbox "
        f"{shlex.quote(session_id)} {shlex.quote(resume)}"
    )


def _codex_command(*, command: str, session_id: str, resume: str, model: str | None) -> str:
    model_arg = f" -m {shlex.quote(model)}" if model is not None else ""
    return (
        f"{shlex.quote(command)}{model_arg} resume "
        f"--dangerously-bypass-approvals-and-sandbox "
        f"{shlex.quote(session_id)} {shlex.quote(resume)}"
    )


def codex_launch_plan(
    *, track: registry.Track, session_id: str, resume: str
) -> CodexLaunchPlan | LaunchProfileProblem:
    profile = track.model_profile
    if profile is None:
        return CodexLaunchPlan(
            command=_bare_codex_command(session_id=session_id, resume=resume),
            env=None,
        )
    if profile["harness"] != "codex":
        return _problem(
            track=track,
            reason=f"harness {profile['harness']!r} cannot relaunch a Codex track",
        )
    model = cast(str, profile["model"])
    wrapper = profile["wrapper"]
    if wrapper is None:
        return CodexLaunchPlan(
            command=_codex_command(
                command="codex",
                model=model,
                session_id=session_id,
                resume=resume,
            ),
            env=MappingProxyType(_scrubbed_env()),
        )
    wrapper_problem = _wrapper_problem(track=track, wrapper=wrapper)
    if wrapper_problem is not None:
        return wrapper_problem
    env = _scrubbed_env()
    env["ANTHROPIC_MODEL"] = model
    return CodexLaunchPlan(
        command=_codex_command(
            command=wrapper,
            model=None,
            session_id=session_id,
            resume=resume,
        ),
        env=MappingProxyType(env),
    )
