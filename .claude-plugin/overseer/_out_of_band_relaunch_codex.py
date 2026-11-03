"""Codex-specific proof and binding for attended relaunches."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

import codex_sessions
import herdr_identity
import pane_router
import registry
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX, SUBMIT_MAX_ENTERS
from _supervisor_launch import canonical_codex_session_id, submit_prompt_result
from _supervisor_prompts import resume_for_track
from out_of_band_relaunch_intent import finish_intent
from out_of_band_relaunch_validation import RelaunchRequest, RelaunchResult

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "codex_rename_wait_bound",
    "confirm_codex_rename",
    "derived_session_name",
    "indexed_codex_thread",
    "relaunch_codex",
    "report_codex_agent_session",
]

_HERDR_REPORT_SOURCE = "overseer"


def derived_session_name(*, sup: Supervisor, track: registry.Track) -> str:
    """Use the collision-aware name that ordinary Codex adoption requires."""
    return registry.tmux_id(
        repo=track.repo,
        topic=track.topic,
        colliding=getattr(sup, "colliding_topics", frozenset()),
    )


def indexed_codex_thread(*, name: str, sup: Supervisor) -> str | None:
    """Read the canonical id currently indexed under exactly ``name``."""
    return canonical_codex_session_id(
        value=codex_sessions.latest_session_for_thread_name(
            thread_name=name,
            codex_home=getattr(sup, "codex_home", ""),
        )
    )


def codex_rename_wait_bound() -> str:
    """The finite confirmation bound shown in the operator result."""
    maximum = RESTART_POLL_MAX * RESTART_POLL_INTERVAL
    return f"{RESTART_POLL_MAX} polls at {RESTART_POLL_INTERVAL:g}s (at most {maximum:g}s)"


def confirm_codex_rename(
    *, name: str, prior_thread: str | None, sup: Supervisor, target: str
) -> str | None:
    """Submit a rename and return only its newly indexed canonical thread id."""
    if not sup.tmux.bracketed_paste(session=target, text=f"/rename {name}"):
        return None
    for attempt in range(RESTART_POLL_MAX):
        if attempt < SUBMIT_MAX_ENTERS:
            _ = sup.tmux.send_keys(session=target, keys="Enter")
        sup.sleep(RESTART_POLL_INTERVAL)
        thread_id = indexed_codex_thread(name=name, sup=sup)
        if thread_id is not None and thread_id != prior_thread:
            return thread_id
    return None


def report_codex_agent_session(*, sup: Supervisor, target: str, thread_id: str) -> bool:
    """Report and re-read a confirmed Codex id at only the exact Herdr pane."""
    decoded = herdr_identity.decode_target(value=target)
    if decoded.herdr is None:
        return True
    completed = subprocess.run(  # noqa: S603 - fixed Herdr command and exact pane id.
        (
            "herdr",
            "pane",
            "report-agent-session",
            "--source",
            _HERDR_REPORT_SOURCE,
            "--agent",
            "codex",
            "--agent-session-id",
            thread_id,
            decoded.herdr.pane_id,
        ),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=RESTART_POLL_INTERVAL,
    )
    driver = cast(pane_router.MixedPaneDriver, sup.tmux)
    return completed.returncode == 0 and driver.pane_agent_session(session=target) == thread_id


def _failed(
    *, intent: Path, track: registry.Track, request: RelaunchRequest, outcome: str, message: str
) -> RelaunchResult:
    finish_intent(
        error=message,
        outcome=outcome,
        path=intent,
        request=request,
        track=track,
    )
    return RelaunchResult(ok=False, message=message)


def _rebind(*, track: registry.Track, target: str, thread_id: str) -> bool:
    rebound = replace(track, tmux=target, observed_session_identity=f"codex:{thread_id}")
    return registry.upsert_mapping(
        track=rebound,
        update_fields=frozenset({"tmux", "observed_session_identity", "model_profile"}),
        allow_retarget=True,
    )


def relaunch_codex(
    *,
    intent: Path,
    profile_track: registry.Track,
    request: RelaunchRequest,
    sup: Supervisor,
    track: registry.Track,
) -> RelaunchResult:
    """Bind, report, resume and rebind one freshly launched Codex session."""
    name = derived_session_name(sup=sup, track=track)
    prior_thread = indexed_codex_thread(name=name, sup=sup)
    thread_id = confirm_codex_rename(
        name=name,
        prior_thread=prior_thread,
        sup=sup,
        target=request.target,
    )
    if thread_id is None:
        observed = indexed_codex_thread(name=name, sup=sup)
        return _failed(
            intent=intent,
            track=track,
            request=request,
            outcome="rename_unconfirmed",
            message=(
                f"relaunch FAILED: Codex rename for pane {request.target} was not confirmed "
                f"within {codex_rename_wait_bound()}; observed thread {observed or 'none'}"
            ),
        )
    if not report_codex_agent_session(sup=sup, target=request.target, thread_id=thread_id):
        return _failed(
            intent=intent,
            track=track,
            request=request,
            outcome="agent_session_report_failed",
            message=(
                f"relaunch FAILED: could not report Codex thread {thread_id} "
                f"for pane {request.target}"
            ),
        )
    resume = resume_for_track(track=track)
    if resume is None:
        return _failed(
            intent=intent,
            track=track,
            request=request,
            outcome="resume_unavailable",
            message="relaunch FAILED: no resume prompt",
        )
    submitted = submit_prompt_result(sup=sup, target=request.target, text=resume, expect_codex=True)
    if not submitted.submitted or not _rebind(
        track=profile_track,
        target=request.target,
        thread_id=thread_id,
    ):
        return _failed(
            intent=intent,
            track=track,
            request=request,
            outcome="resume_or_rebind_failed",
            message="relaunch FAILED: resume or mapping rebind was unconfirmed",
        )
    finish_intent(outcome="succeeded", path=intent, request=request, track=track)
    return RelaunchResult(
        ok=True,
        message=(
            f"relaunched {track.repo}::{track.topic} at {request.target}; Codex rename "
            f"confirmed within {codex_rename_wait_bound()}"
        ),
    )
