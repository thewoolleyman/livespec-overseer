"""The deliberately-attended, non-destructive relaunch operator surface."""
# livespec-lloc-soft-band-owner: overseer-iuq23z

from __future__ import annotations

import json
import os
import shlex
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

import herdr_identity
import pane_router
import registry
import signals
import tmuxio_env
from _supervisor_launch import await_input_box, await_pane, submit_prompt_result
from _supervisor_launch_profile import ClaudeLaunchPlan, LaunchProfileProblem, claude_launch_plan
from _supervisor_prompts import resume_for_track

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["RelaunchRequest", "RelaunchResult", "relaunch"]

_ACTION = "sanctioned-out-of-band-relaunch"
_INTENT_NAME = ".out-of-band-relaunch-intent.json"


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


def _matching_track(*, topic: str, tracks: list[registry.Track]) -> registry.Track | None:
    matches = [track for track in tracks if track.topic == topic and track.assigned]
    return matches[0] if len(matches) == 1 else None


def _same_backend(*, recorded: str, target: str) -> bool:
    source = herdr_identity.decode_target(value=recorded)
    destination = herdr_identity.decode_target(value=target)
    if source.error or destination.error:
        return False
    if source.tmux is not None:
        if destination.tmux is None:
            return False
        return (
            source.tmux.socket_path,
            source.tmux.server_pid,
            source.tmux.server_starttime,
        ) == (
            destination.tmux.socket_path,
            destination.tmux.server_pid,
            destination.tmux.server_starttime,
        )
    if source.herdr is None:
        return destination.herdr is None
    if destination.herdr is None:
        return False
    return (
        source.herdr.socket_path,
        source.herdr.server_pid,
        source.herdr.server_starttime,
    ) == (
        destination.herdr.socket_path,
        destination.herdr.server_pid,
        destination.herdr.server_starttime,
    )


def _target_is_idle_shell(*, sup: Supervisor, target: str) -> bool:
    resolved = sup.tmux.pane_id(session=target)
    return resolved == target and signals.pane_is_shell(
        pane_current_command=sup.tmux.pane_current_command(session=target)
    )


def _profile_for_request(
    *, track: registry.Track, request: RelaunchRequest
) -> registry.Track | RelaunchResult:
    recorded = track.model_profile
    runtime = request.runtime or (None if recorded is None else recorded["harness"])
    if runtime is None and any(value is not None for value in (request.model, request.wrapper)):
        runtime = "claude"
    if runtime is not None and runtime != "claude":
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


def _intent_path(*, track: registry.Track) -> Path:
    return Path(track.repo) / "tmp" / "overseer" / track.topic / _INTENT_NAME


def _durable_json(*, path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        _ = handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    _ = temporary.replace(path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _start_intent(*, track: registry.Track, request: RelaunchRequest) -> Path:
    path = _intent_path(track=track)
    _durable_json(
        path=path,
        value={
            "action": _ACTION,
            "invoker": request.invoker,
            "outcome": None,
            "target": request.target,
            "track": f"{track.repo}::{track.topic}",
        },
    )
    return path


def _finish_intent(
    *, path: Path, track: registry.Track, request: RelaunchRequest, outcome: str
) -> None:
    _durable_json(
        path=path,
        value={
            "action": _ACTION,
            "invoker": request.invoker,
            "outcome": outcome,
            "target": request.target,
            "track": f"{track.repo}::{track.topic}",
        },
    )


def _launch_at_shell(
    *, sup: Supervisor, track: registry.Track, target: str, plan: ClaudeLaunchPlan
) -> bool:
    environment_launch = tmuxio_env.with_env_delta(command=plan.command, env=plan.env)
    command = f"cd -- {shlex.quote(track.repo)} && {environment_launch}"
    return sup.tmux.bracketed_paste(session=target, text=command) and sup.tmux.send_keys(
        session=target, keys="Enter"
    )


def _identity_after_launch(*, sup: Supervisor, track: registry.Track, target: str) -> str | None:
    pane_router.register_coordinates(driver=sup.tmux, coordinates=(target,))
    sup.refresh_claude_status()
    return sup.claude_identity_by_session.get((target, track.topic))


def _rebind(*, track: registry.Track, target: str, identity: str) -> bool:
    rebound = replace(track, tmux=target, observed_session_identity=identity)
    return registry.upsert_mapping(
        track=rebound,
        update_fields=frozenset({"tmux", "observed_session_identity", "model_profile"}),
        allow_retarget=True,
    )


def _refuse(*, message: str) -> RelaunchResult:
    return RelaunchResult(ok=False, message=f"relaunch REFUSED: {message}")


def _validated_launch(
    *, request: RelaunchRequest, sup: Supervisor, tracks: list[registry.Track] | None
) -> tuple[registry.Track, registry.Track, ClaudeLaunchPlan] | RelaunchResult:
    track = _matching_track(
        topic=request.topic,
        tracks=registry.read_valid_mapping(store_path=sup.store_path) if tracks is None else tracks,
    )
    if track is None or not registry.epic_is_resolved(epic=track.epic):
        return _refuse(message="topic has no uniquely mapped track with a recorded epic")
    recorded_target = track.tmux
    if recorded_target is None or not _same_backend(
        recorded=recorded_target, target=request.target
    ):
        return _refuse(message="target is not on the recorded backend instance")
    if not _target_is_idle_shell(sup=sup, target=request.target):
        return _refuse(message="target is not an idle interactive shell")
    profile_track = _profile_for_request(track=track, request=request)
    if isinstance(profile_track, RelaunchResult):
        return profile_track
    plan = claude_launch_plan(track=profile_track)
    if isinstance(plan, LaunchProfileProblem):
        return _refuse(message=plan.message)
    return track, profile_track, plan


def _record_failed_launch(
    *, intent: Path, track: registry.Track, request: RelaunchRequest, outcome: str, message: str
) -> RelaunchResult:
    _finish_intent(path=intent, track=track, request=request, outcome=outcome)
    return RelaunchResult(ok=False, message=message)


def relaunch(
    *, request: RelaunchRequest, sup: Supervisor, tracks: list[registry.Track] | None = None
) -> RelaunchResult:
    """Launch a non-Codex profile at a separately-proven idle pane.

    Every refusal precedes the intent record and any terminal input.  This is
    deliberately not a restart: it neither signals a process nor reads or
    changes the track's state declaration.
    """
    validated = _validated_launch(request=request, sup=sup, tracks=tracks)
    if isinstance(validated, RelaunchResult):
        return validated
    track, profile_track, plan = validated
    intent = _start_intent(track=track, request=request)
    if not _launch_at_shell(sup=sup, track=track, target=request.target, plan=plan):
        return _record_failed_launch(
            intent=intent,
            track=track,
            request=request,
            outcome="launch_failed",
            message="relaunch FAILED: launch input was not accepted",
        )
    if not await_pane(sup=sup, target=request.target, is_ready=signals.pane_is_claude):
        return _record_failed_launch(
            intent=intent,
            track=track,
            request=request,
            outcome="launch_unconfirmed",
            message="relaunch FAILED: Claude did not appear",
        )
    _ = await_input_box(sup=sup, target=request.target)
    resume = resume_for_track(track=track)
    if resume is None:
        return _record_failed_launch(
            intent=intent,
            track=track,
            request=request,
            outcome="resume_unavailable",
            message="relaunch FAILED: no resume prompt",
        )
    submitted = submit_prompt_result(sup=sup, target=request.target, text=resume)
    identity = _identity_after_launch(sup=sup, track=track, target=request.target)
    if (
        not submitted.submitted
        or identity is None
        or not _rebind(track=profile_track, target=request.target, identity=identity)
    ):
        return _record_failed_launch(
            intent=intent,
            track=track,
            request=request,
            outcome="resume_or_rebind_failed",
            message="relaunch FAILED: resume or mapping rebind was unconfirmed",
        )
    _finish_intent(path=intent, track=track, request=request, outcome="succeeded")
    return RelaunchResult(
        ok=True, message=f"relaunched {track.repo}::{track.topic} at {request.target}"
    )
