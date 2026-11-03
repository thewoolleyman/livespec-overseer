"""Preflight validation for the attended, non-destructive relaunch surface."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import herdr_identity
import registry
import signals
from _supervisor_launch_profile import (
    ClaudeLaunchPlan,
    CodexLaunchPlan,
    LaunchProfileProblem,
    claude_launch_plan,
    codex_fresh_launch_plan,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "RelaunchRequest",
    "RelaunchResult",
    "matching_track",
    "profile_for_request",
    "same_backend",
    "target_is_idle_shell",
    "validated_launch",
]


@dataclass(frozen=True, kw_only=True)
class RelaunchRequest:
    topic: str
    target: str
    invoker: str
    runtime: str | None = None
    model: str | None = None
    wrapper: str | None = None


@dataclass(frozen=True, kw_only=True)
class RelaunchResult:
    ok: bool
    message: str


def matching_track(*, topic: str, tracks: list[registry.Track]) -> registry.Track | None:
    matches = [track for track in tracks if track.topic == topic and track.assigned]
    return matches[0] if len(matches) == 1 else None


def same_backend(*, recorded: str, target: str) -> bool:
    source = herdr_identity.decode_target(value=recorded)
    destination = herdr_identity.decode_target(value=target)
    if source.error or destination.error:
        return False
    if source.tmux_session:
        return source.tmux_session == target
    source_instance = source.tmux or source.herdr
    destination_instance = destination.tmux or destination.herdr
    if (
        source_instance is None
        or destination_instance is None
        or source.backend != destination.backend
    ):
        return False
    return (
        source_instance.socket_path,
        source_instance.server_pid,
        source_instance.server_starttime,
    ) == (
        destination_instance.socket_path,
        destination_instance.server_pid,
        destination_instance.server_starttime,
    )


def target_is_idle_shell(*, sup: Supervisor, target: str) -> bool:
    resolved = sup.tmux.pane_id(session=target)
    return resolved == target and signals.pane_is_shell(
        pane_current_command=sup.tmux.pane_current_command(session=target)
    )


def profile_for_request(
    *, track: registry.Track, request: RelaunchRequest
) -> registry.Track | RelaunchResult:
    recorded = track.model_profile
    runtime = request.runtime or (None if recorded is None else recorded["harness"])
    if runtime is None and any(value is not None for value in (request.model, request.wrapper)):
        runtime = "claude"
    if (
        runtime == "codex"
        and request.model is None
        and recorded is not None
        and recorded["harness"] != "codex"
    ):
        runtime = "codex transition without a Codex model"
    if runtime is not None and runtime not in {"claude", "codex"}:
        return RelaunchResult(
            ok=False, message=f"relaunch REFUSED: unsupported runtime {runtime!r}"
        )
    if runtime is None:
        return track
    model = request.model or (None if recorded is None else recorded["model"])
    if not model:
        return RelaunchResult(ok=False, message="relaunch REFUSED: profile has no model token")
    wrapper = (
        request.wrapper
        if request.wrapper is not None
        else (None if recorded is None else recorded["wrapper"])
    )
    return replace(
        track,
        model_profile={"harness": runtime, "model": model, "wrapper": wrapper},
    )


def _refuse(*, message: str) -> RelaunchResult:
    return RelaunchResult(ok=False, message=f"relaunch REFUSED: {message}")


def validated_launch(
    *, request: RelaunchRequest, sup: Supervisor, tracks: list[registry.Track] | None
) -> tuple[registry.Track, registry.Track, ClaudeLaunchPlan | CodexLaunchPlan] | RelaunchResult:
    track = matching_track(
        topic=request.topic,
        tracks=registry.read_valid_mapping(store_path=sup.store_path) if tracks is None else tracks,
    )
    if track is None or not registry.epic_is_resolved(epic=track.epic):
        return _refuse(message="topic has no uniquely mapped track with a recorded epic")
    recorded_target = track.tmux
    if recorded_target is None or not same_backend(recorded=recorded_target, target=request.target):
        return _refuse(message="target is not on the recorded backend instance")
    if not target_is_idle_shell(sup=sup, target=request.target):
        return _refuse(message="target is not an idle interactive shell")
    profile_track = profile_for_request(track=track, request=request)
    if isinstance(profile_track, RelaunchResult):
        return profile_track
    plan = (
        codex_fresh_launch_plan(track=profile_track)
        if profile_track.model_profile is not None
        and profile_track.model_profile["harness"] == "codex"
        else claude_launch_plan(track=profile_track)
    )
    if isinstance(plan, LaunchProfileProblem):
        return _refuse(message=plan.message)
    return track, profile_track, plan
