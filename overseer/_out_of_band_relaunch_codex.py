"""Codex evidence and backend reporting for attended relaunches."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

import codex_session_index
import herdr_identity
import herdr_write
import pane_router
import registry
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX
from _supervisor_launch import canonical_codex_session_id
from out_of_band_relaunch_actions import RelaunchActions
from out_of_band_relaunch_validation import RelaunchRequest, RelaunchResult

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CodexRelaunch",
    "codex_rename_wait_bound",
    "codex_thread_ids",
    "confirm_codex_rename",
    "derived_session_name",
    "observed_codex_thread",
    "relaunch_codex",
    "report_codex_agent_session",
]

_HERDR_REPORT_SOURCE = "overseer"


@dataclass(frozen=True, kw_only=True)
class CodexRelaunch:
    """The launch-local evidence carried from the generic entrypoint to the Codex arm."""

    intent: Path
    name: str
    prior_thread_ids: frozenset[str]
    profile_track: registry.Track
    request: RelaunchRequest
    track: registry.Track


def derived_session_name(*, sup: Supervisor, track: registry.Track) -> str:
    """Use normal track adoption's collision-aware session-name derivation."""
    return registry.tmux_id(
        repo=track.repo,
        topic=track.topic,
        colliding=sup.colliding_topics,
    )


def _index(*, sup: Supervisor) -> dict[str, str]:
    if sup.codex_home is None:
        return {}
    return codex_session_index.read_thread_names(codex_home=sup.codex_home)


def codex_thread_ids(*, sup: Supervisor) -> frozenset[str]:
    """Capture every canonical thread known before this launch begins."""
    return frozenset(
        canonical
        for thread_id in _index(sup=sup)
        if (canonical := canonical_codex_session_id(value=thread_id)) is not None
    )


def observed_codex_thread(*, name: str, sup: Supervisor) -> str | None:
    """Return the one indexed canonical thread currently named exactly ``name``."""
    threads = {
        canonical
        for thread_id, thread_name in _index(sup=sup).items()
        if thread_name == name
        and (canonical := canonical_codex_session_id(value=thread_id)) is not None
    }
    return next(iter(threads)) if len(threads) == 1 else None


def codex_rename_wait_bound() -> str:
    """State the finite rename-confirmation wait in operator-facing output."""
    maximum = RESTART_POLL_MAX * RESTART_POLL_INTERVAL
    return f"{RESTART_POLL_MAX} polls at {RESTART_POLL_INTERVAL:g}s (at most {maximum:g}s)"


def confirm_codex_rename(
    *, name: str, prior_thread_ids: frozenset[str], sup: Supervisor, target: str
) -> str | None:
    """Confirm exactly one newly indexed thread has the launch's derived name."""
    if not sup.tmux.bracketed_paste(session=target, text=f"/rename {name}"):
        return None
    if not sup.tmux.send_keys(session=target, keys="Enter"):
        return None
    for _ in range(RESTART_POLL_MAX):
        fresh = codex_thread_ids(sup=sup) - prior_thread_ids
        matches = {
            thread_id
            for thread_id, thread_name in _index(sup=sup).items()
            if thread_name == name and thread_id in fresh
        }
        if len(matches) == 1:
            return next(iter(matches))
        sup.sleep(RESTART_POLL_INTERVAL)
    return None


def report_codex_agent_session(*, sup: Supervisor, target: str, thread_id: str) -> bool:
    """Report a confirmed Codex thread only to its exact Herdr pane."""
    decoded = herdr_identity.decode_target(value=target)
    if decoded.herdr is None:
        return True
    driver = cast(pane_router.MixedPaneDriver, sup.tmux)
    writer = cast(herdr_write.HerdrWriter, driver.herdr_writer)
    return writer.report_agent_session(
        target=decoded.herdr,
        source=_HERDR_REPORT_SOURCE,
        agent_session_id=thread_id,
    ).ok


def _failed(
    *,
    actions: RelaunchActions,
    relaunch: CodexRelaunch,
    outcome: str,
    message: str,
) -> RelaunchResult:
    actions.finish_intent(
        error=message,
        outcome=outcome,
        path=relaunch.intent,
        request=relaunch.request,
        track=relaunch.track,
    )
    return RelaunchResult(ok=False, message=message)


def _deliver_resume(
    *,
    actions: RelaunchActions,
    relaunch: CodexRelaunch,
    sup: Supervisor,
    thread_id: str,
) -> RelaunchResult:
    if not report_codex_agent_session(sup=sup, target=relaunch.request.target, thread_id=thread_id):
        return _failed(
            actions=actions,
            relaunch=relaunch,
            outcome="agent_session_report_failed",
            message=(
                f"relaunch FAILED: could not report Codex thread {thread_id} "
                f"for pane {relaunch.request.target}"
            ),
        )
    resume = actions.resume_for_track(track=relaunch.track)
    if resume is None:
        return _failed(
            actions=actions,
            relaunch=relaunch,
            outcome="resume_unavailable",
            message="relaunch FAILED: no resume prompt",
        )
    submitted = actions.submit_prompt_result(
        sup=sup,
        target=relaunch.request.target,
        text=resume,
        expect_codex=True,
    )
    rebound = replace(
        relaunch.profile_track,
        tmux=relaunch.request.target,
        observed_session_identity=f"codex:{thread_id}",
    )
    if not submitted.submitted or not actions.rebind(
        track=rebound,
        target=relaunch.request.target,
        identity=f"codex:{thread_id}",
    ):
        return _failed(
            actions=actions,
            relaunch=relaunch,
            outcome="resume_or_rebind_failed",
            message="relaunch FAILED: resume or mapping rebind was unconfirmed",
        )
    actions.finish_intent(
        outcome="succeeded",
        path=relaunch.intent,
        request=relaunch.request,
        track=relaunch.track,
    )
    return RelaunchResult(
        ok=True,
        message=(
            f"relaunched {relaunch.track.repo}::{relaunch.track.topic} at "
            f"{relaunch.request.target}; Codex rename "
            f"confirmed within {codex_rename_wait_bound()}"
        ),
    )


def relaunch_codex(
    *,
    actions: RelaunchActions,
    relaunch: CodexRelaunch,
    sup: Supervisor,
) -> RelaunchResult:
    """Confirm the fresh name before reporting, resuming and rebinding the track."""
    thread_id = confirm_codex_rename(
        name=relaunch.name,
        prior_thread_ids=relaunch.prior_thread_ids,
        sup=sup,
        target=relaunch.request.target,
    )
    if thread_id is None:
        observed = observed_codex_thread(name=relaunch.name, sup=sup)
        return _failed(
            actions=actions,
            relaunch=relaunch,
            outcome="rename_unconfirmed",
            message=(
                "relaunch FAILED: Codex rename for pane "
                f"{relaunch.request.target} was not confirmed "
                f"within {codex_rename_wait_bound()}; observed thread {observed or 'none'}"
            ),
        )
    return _deliver_resume(
        actions=actions,
        relaunch=relaunch,
        sup=sup,
        thread_id=thread_id,
    )
