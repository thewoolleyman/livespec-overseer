"""Claude launch-profile planning for restart and reboot recovery."""
# livespec-lloc-soft-band-owner: overseer-6m2h

from __future__ import annotations

import os
import shlex
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import registry
from _supervisor_launch_profile_capture import (
    LaunchProfileProblem,
    apply_runtime_model,
    read_launch_profile,
)
from _supervisor_statusline_model import rendered_statusline_model

__all__: list[str] = [
    "CLAUDE_CONTROLLED_ENV",
    "CODEX_APPROVALS_FLAG",
    "DEFAULT_START_MODEL",
    "PLAN_UNATTENDED_ENV",
    "ClaudeLaunchPlan",
    "CodexLaunchPlan",
    "LaunchProfileProblem",
    "apply_runtime_model",
    "claude_launch_plan",
    "codex_fresh_launch_plan",
    "codex_launch_plan",
    "preflight_launch_command",
    "read_launch_profile",
    "rendered_statusline_model",
]

CLAUDE_CONTROLLED_ENV = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_DISABLE_1M_CONTEXT",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
)
PLAN_UNATTENDED_ENV = "LIVESPEC_PLAN_UNATTENDED"

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


def _with_unattended_restart_env(
    *, env: Mapping[str, str | None], daemon_restart: bool
) -> Mapping[str, str | None]:
    if not daemon_restart:
        return env
    merged = dict(env)
    merged[PLAN_UNATTENDED_ENV] = "1"
    return MappingProxyType(merged)


def _claude_command(*, topic: str, model: str | None) -> str:
    """The Claude launch command, with an explicit model only when one is given."""
    model_arg = "" if model is None else f"--model {shlex.quote(model)} "
    return f"claude {model_arg}--dangerously-skip-permissions -n {shlex.quote(topic)}"


def _launch_search_path() -> str:
    entries = os.environ.get("PATH", "")
    home_local = Path.home() / ".local" / "bin"
    return os.pathsep.join(part for part in (entries, str(home_local)) if part)


def _binary_problem(*, binary: str, path: str) -> LaunchProfileProblem:
    return LaunchProfileProblem(
        message=("launch_binary_not_resolvable " f"binary={binary} path={path}")
    )


def preflight_launch_command(*, command: str) -> str | LaunchProfileProblem:
    parts = shlex.split(command)
    if not parts:
        return _binary_problem(binary="", path=_launch_search_path())
    binary = parts[0]
    if Path(binary).is_absolute():
        path = Path(binary)
        if path.is_file() and os.access(path, os.X_OK):
            return shlex.join(parts)
        return _binary_problem(binary=binary, path=_launch_search_path())
    search_path = _launch_search_path()
    resolved = shutil.which(binary, path=search_path)
    if resolved is None:
        return _binary_problem(binary=binary, path=search_path)
    return shlex.join([resolved, *parts[1:]])


def _problem(*, track: registry.Track, reason: str) -> LaunchProfileProblem:
    return LaunchProfileProblem(
        message=f"stale launch profile for {track.repo}::{track.topic}: {reason}"
    )


def _wrapper_problem(*, track: registry.Track, wrapper: str) -> LaunchProfileProblem | None:
    path = Path(wrapper)
    if path.is_file() and os.access(path, os.X_OK):
        return None
    return _problem(track=track, reason=f"wrapper {wrapper!r} does not exist or is not executable")


def _claude_launch_plan(
    *,
    command: str,
    env: Mapping[str, str | None],
    daemon_restart: bool,
    preflight: bool,
) -> ClaudeLaunchPlan | LaunchProfileProblem:
    if not preflight:
        return ClaudeLaunchPlan(
            command=command,
            env=_with_unattended_restart_env(
                env=env,
                daemon_restart=daemon_restart,
            ),
        )
    preflighted = preflight_launch_command(command=command)
    if isinstance(preflighted, LaunchProfileProblem):
        return preflighted
    return ClaudeLaunchPlan(
        command=preflighted,
        env=_with_unattended_restart_env(
            env=env,
            daemon_restart=daemon_restart,
        ),
    )


def claude_launch_plan(
    *, track: registry.Track, start: bool = False, daemon_restart: bool = False
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
        return _claude_launch_plan(
            command=_claude_command(
                topic=track.topic, model=DEFAULT_START_MODEL if start else None
            ),
            env=_scrubbed_env(),
            daemon_restart=daemon_restart,
            preflight=start,
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
        return _claude_launch_plan(
            command=_claude_command(topic=track.topic, model=model),
            env=MappingProxyType(env),
            daemon_restart=daemon_restart,
            preflight=False,
        )
    wrapper_problem = _wrapper_problem(track=track, wrapper=wrapper)
    if wrapper_problem is not None:
        return wrapper_problem
    env["ANTHROPIC_MODEL"] = model
    return _claude_launch_plan(
        command=(
            f"{shlex.quote(wrapper)} "
            f"--dangerously-skip-permissions -n {shlex.quote(track.topic)}"
        ),
        env=MappingProxyType(env),
        daemon_restart=daemon_restart,
        preflight=False,
    )


CODEX_APPROVALS_FLAG = "--dangerously-bypass-approvals-and-sandbox"


@dataclass(frozen=True, kw_only=True)
class _CodexInvocation:
    """The profile-derived half of a Codex command: WHAT to run and under WHICH model.

    Both Codex arms resolve the profile identically — that resolution is about the
    harness, the wrapper and the model, none of which care whether the session being
    launched is fresh or resumed. Only the SUBCOMMAND differs, so the arms share this
    and render their own tail.
    """

    command: str
    model: str | None
    env: Mapping[str, str | None]


def _codex_prefix(*, invocation: _CodexInvocation) -> str:
    model_arg = "" if invocation.model is None else f" -m {shlex.quote(invocation.model)}"
    return f"{shlex.quote(invocation.command)}{model_arg}"


def _codex_invocation(
    *, track: registry.Track, daemon_restart: bool
) -> _CodexInvocation | LaunchProfileProblem:
    profile = track.model_profile
    if profile is None:
        return _CodexInvocation(
            command="codex",
            model=None,
            env=_with_unattended_restart_env(
                env=_scrubbed_env(),
                daemon_restart=daemon_restart,
            ),
        )
    if profile["harness"] != "codex":
        return _problem(
            track=track,
            reason=f"harness {profile['harness']!r} cannot relaunch a Codex track",
        )
    model = cast(str, profile["model"])
    wrapper = profile["wrapper"]
    if wrapper is None:
        return _CodexInvocation(
            command="codex",
            model=model,
            env=_with_unattended_restart_env(
                env=MappingProxyType(_scrubbed_env()),
                daemon_restart=daemon_restart,
            ),
        )
    wrapper_problem = _wrapper_problem(track=track, wrapper=wrapper)
    if wrapper_problem is not None:
        return wrapper_problem
    env = _scrubbed_env()
    # BOTH mechanisms are here, and only ONE of them re-asserts the model on this arm.
    #
    # The env assignment is the set-or-scrub rule the specification binds to every
    # relaunch of every harness: never inherit these passively. It is NOT what
    # preserves the model here. The Claude wrapper arm gets model preservation from
    # the same assignment for free, because `claude-local-llm` DEFERS to an inherited
    # value — the deference IS the mechanism. `codex-local-llm` has no such deference:
    # it execs `codex -c model_provider=local-llm-fleet "$@"` and never reads
    # ANTHROPIC_MODEL, leaving Codex's own model picker in charge. Relying on the env
    # alone preserved the PROVIDER while silently dropping the recorded MODEL.
    #
    # So the model rides `-m` through the wrapper's `"$@"`, exactly as on the bare
    # codex arm — a mechanism the real consumer honours.
    env["ANTHROPIC_MODEL"] = model
    return _CodexInvocation(
        command=wrapper,
        model=model,
        env=_with_unattended_restart_env(
            env=MappingProxyType(env),
            daemon_restart=daemon_restart,
        ),
    )


def codex_launch_plan(
    *, track: registry.Track, session_id: str, resume: str, daemon_restart: bool = False
) -> CodexLaunchPlan | LaunchProfileProblem:
    """RESUME the exact prior rollout — the CRASH-RECOVERY arm.

    ``codex resume <uuid>`` reattaches that rollout AND the context it accumulated,
    which is precisely what recovery wants: the conversation a crash interrupted is
    restored rather than re-derived. It is the WRONG arm for a wrap-up restart, whose
    whole purpose is a reset context window — see :func:`codex_fresh_launch_plan`.
    """
    invocation = _codex_invocation(track=track, daemon_restart=daemon_restart)
    if isinstance(invocation, LaunchProfileProblem):
        return invocation
    return CodexLaunchPlan(
        command=(
            f"{_codex_prefix(invocation=invocation)} resume {CODEX_APPROVALS_FLAG} "
            f"{shlex.quote(session_id)} {shlex.quote(resume)}"
        ),
        env=invocation.env,
    )


def codex_fresh_launch_plan(
    *, track: registry.Track, daemon_restart: bool = False
) -> CodexLaunchPlan | LaunchProfileProblem:
    """Launch a BRAND-NEW Codex session — the WRAP-UP-RESTART arm.

    No ``resume`` subcommand and no positional session id, so Codex opens a rollout of
    its own with an empty context window. That reset IS the deliverable of a wrap-up
    restart: the session declared ``ready`` because it had wound down out of context,
    and handing its successor the predecessor's rollout hands back the same exhausted
    window (measured live 2026-09-10: one rollout resumed four times, 50% → 17%
    remaining, until Codex compacted itself).

    No prompt is passed either. ``codex resume`` can take its kick as an argv
    positional, but a fresh session must first be NAMED — the daemon submits
    ``/rename <topic>`` so the rollout carries durable thread-name evidence — and a
    launch-time prompt would start the model working before that could happen. The
    resume line is therefore pasted after naming, by :mod:`_supervisor_codex_restart`.
    """
    invocation = _codex_invocation(track=track, daemon_restart=daemon_restart)
    if isinstance(invocation, LaunchProfileProblem):
        return invocation
    return CodexLaunchPlan(
        command=f"{_codex_prefix(invocation=invocation)} {CODEX_APPROVALS_FLAG}",
        env=invocation.env,
    )
