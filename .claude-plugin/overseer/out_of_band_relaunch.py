"""The deliberately-attended, non-destructive relaunch operator surface."""

from __future__ import annotations

import shlex
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

import _out_of_band_relaunch_codex
import herdr_identity
import pane_router
import registry
import signals
import tmuxio_env
from _supervisor_launch import await_input_box, await_pane, submit_prompt_result
from _supervisor_launch_profile import ClaudeLaunchPlan, CodexLaunchPlan
from _supervisor_prompts import resume_for_track
from out_of_band_relaunch_intent import finish_intent, start_intent
from out_of_band_relaunch_validation import (
    RelaunchRequest,
    RelaunchResult,
)
from out_of_band_relaunch_validation import (
    matching_track as _matching_track,
)
from out_of_band_relaunch_validation import (
    profile_for_request as _profile_for_request,
)
from out_of_band_relaunch_validation import (
    same_backend as _same_backend,
)
from out_of_band_relaunch_validation import (
    target_is_idle_shell as _target_is_idle_shell,
)
from out_of_band_relaunch_validation import (
    validated_launch as _validated_launch,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["RelaunchRequest", "RelaunchResult", "relaunch"]

_ACTION = "sanctioned-out-of-band-relaunch"

_finish_intent = finish_intent
_start_intent = start_intent
_VALIDATION_SEAMS = (
    _matching_track,
    _profile_for_request,
    _same_backend,
    _target_is_idle_shell,
)


def _launch_at_shell(
    *, sup: Supervisor, track: registry.Track, target: str, plan: ClaudeLaunchPlan | CodexLaunchPlan
) -> bool:
    decoded = herdr_identity.decode_target(value=target)
    if decoded.herdr is not None:
        outcome = cast(pane_router.MixedPaneDriver, sup.tmux).herdr_writer.launch(
            target=decoded.herdr,
            cwd=track.repo,
            command=plan.command,
            env=plan.env or {},
        )
        return outcome.ok
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


def _record_failed_launch(
    *, intent: Path, track: registry.Track, request: RelaunchRequest, outcome: str, message: str
) -> RelaunchResult:
    _finish_intent(
        error=message,
        outcome=outcome,
        path=intent,
        request=request,
        track=track,
    )
    return RelaunchResult(ok=False, message=message)


def _deliver_resume_and_rebind(
    *,
    intent: Path,
    profile_track: registry.Track,
    request: RelaunchRequest,
    sup: Supervisor,
    track: registry.Track,
) -> RelaunchResult:
    if not await_input_box(sup=sup, target=request.target):
        return _record_failed_launch(
            intent=intent,
            track=track,
            request=request,
            outcome="resume_input_unavailable",
            message="relaunch FAILED: Claude input box did not become ready",
        )
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
    _finish_intent(
        outcome="succeeded",
        path=intent,
        request=request,
        track=track,
    )
    return RelaunchResult(
        ok=True, message=f"relaunched {track.repo}::{track.topic} at {request.target}"
    )


def _is_codex(*, track: registry.Track) -> bool:
    return track.model_profile is not None and track.model_profile["harness"] == "codex"


def relaunch(
    *, request: RelaunchRequest, sup: Supervisor, tracks: list[registry.Track] | None = None
) -> RelaunchResult:
    """Launch a profile at a separately-proven idle pane.

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
    codex = _is_codex(track=profile_track)
    if not await_pane(
        sup=sup,
        target=request.target,
        is_ready=signals.pane_is_codex if codex else signals.pane_is_claude,
    ):
        return _record_failed_launch(
            intent=intent,
            track=track,
            request=request,
            outcome="launch_unconfirmed",
            message=f"relaunch FAILED: {'Codex' if codex else 'Claude'} did not appear",
        )
    if codex:
        return _out_of_band_relaunch_codex.relaunch_codex(
            intent=intent,
            profile_track=profile_track,
            request=request,
            sup=sup,
            track=track,
        )
    return _deliver_resume_and_rebind(
        intent=intent,
        profile_track=profile_track,
        request=request,
        sup=sup,
        track=track,
    )
