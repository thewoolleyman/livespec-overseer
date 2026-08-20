"""Claude launch-profile planning for restart and reboot recovery."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi.3

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import registry
from _seams import PidToOptionalBytes, PidToOptionalInt
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


@dataclass(frozen=True, kw_only=True)
class LaunchProfileProblem:
    message: str


_SHELL_BASENAMES = frozenset({"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"})
_WRAPPER_ENV_KEY = "LIVESPEC_LOCAL_LLM_WRAPPER"


def _split_nul_bytes(*, data: bytes | None) -> list[str]:
    if data is None:
        return []
    return [part.decode(errors="replace") for part in data.split(b"\0") if part]


def _env_from_bytes(*, data: bytes | None) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in _split_nul_bytes(data=data):
        key, sep, value = item.partition("=")
        if sep:
            env[key] = value
    return env


def _model_from_argv(*, argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value == "--model" and index + 1 < len(argv):
            return argv[index + 1]
        if value == "-m" and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith("--model="):
            return value.partition("=")[2]
    return None


def _non_anthropic_base_url(*, base_url: str | None) -> bool:
    if not base_url:
        return False
    return "anthropic.com" not in base_url.lower()


def _wrapper_from_parent_chain(
    *,
    pid: int,
    pane_pid: int | None,
    ppid_of: PidToOptionalInt,
    cmdline_of: PidToOptionalBytes,
) -> str | None:
    current = pid
    seen: set[int] = set()
    for _ in range(64):
        parent = ppid_of(pid=current)
        if parent is None or parent <= 0 or parent == pane_pid or parent in seen:
            return None
        seen.add(parent)
        argv = _split_nul_bytes(data=cmdline_of(pid=parent))
        if argv and Path(argv[0]).name not in _SHELL_BASENAMES:
            return argv[0]
        current = parent
    return None


def _wrapper_from_local_router(
    *,
    env: Mapping[str, str],
    pid: int,
    pane_pid: int | None,
    ppid_of: PidToOptionalInt,
    cmdline_of: PidToOptionalBytes,
) -> str | None:
    wrapper = env.get(_WRAPPER_ENV_KEY)
    if wrapper:
        return wrapper
    return _wrapper_from_parent_chain(
        pid=pid,
        pane_pid=pane_pid,
        ppid_of=ppid_of,
        cmdline_of=cmdline_of,
    )


def read_launch_profile(
    *,
    pid: int,
    harness: str,
    pane_pid: int | None,
    cmdline_of: PidToOptionalBytes,
    environ_of: PidToOptionalBytes,
    ppid_of: PidToOptionalInt,
) -> dict[str, str | None] | LaunchProfileProblem:
    """Read a live process's restart launch profile from ``/proc`` seams."""
    argv = _split_nul_bytes(data=cmdline_of(pid=pid))
    env = _env_from_bytes(data=environ_of(pid=pid))
    model = _model_from_argv(argv=argv) or env.get("ANTHROPIC_MODEL")
    if not model:
        return LaunchProfileProblem(message=f"launch profile for pid {pid} has no model token")
    wrapper = (
        _wrapper_from_local_router(
            env=env,
            pid=pid,
            pane_pid=pane_pid,
            ppid_of=ppid_of,
            cmdline_of=cmdline_of,
        )
        if _non_anthropic_base_url(base_url=env.get("ANTHROPIC_BASE_URL"))
        else None
    )
    return {"harness": harness, "model": model, "wrapper": wrapper}


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
