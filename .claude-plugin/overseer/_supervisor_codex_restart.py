"""Codex-specific restart arm for the overseer supervisor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_state
import registry
import signals
from _supervisor_config import track_key
from _supervisor_launch_profile import CodexLaunchPlan
from _supervisor_prompts import resume_for_track
from _supervisor_statusline_model import restart_blocked_by_statusline_mismatch

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["do_codex_restart"]


def _alert_missing_live(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message="respawned pane has no live Codex process; keeping the ready declaration",
        condition="codex-post-respawn-live-missing",
    )


def _post_respawn_live_process(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    session_id: str,
) -> bool:
    sup.refresh_codex_sessions()
    post_respawn_live = sup.live_codex.get((session, track.topic))
    return (
        post_respawn_live is not None
        and post_respawn_live.session_id == session_id
        and signals.path_in_repo(pane_current_path=post_respawn_live.cwd, repo=track.repo)
    )


def _codex_launch_plan_for_restart(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    session_id: str,
    resume: str,
) -> CodexLaunchPlan | None:
    launch = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id=session_id,
        resume=resume,
    )
    if not isinstance(launch, CodexLaunchPlan):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=f"{launch.message}; keeping the ready declaration so it retries",
            condition="stale-launch-profile",
        )
        return None
    if restart_blocked_by_statusline_mismatch(
        sup=sup,
        track=track,
        target=target,
        session=session,
    ):
        return None
    return launch


def _respawn_verified(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    session: str,
    session_id: str,
    resume: str,
) -> bool:
    launch = _codex_launch_plan_for_restart(
        sup=sup,
        track=track,
        target=target,
        session=session,
        session_id=session_id,
        resume=resume,
    )
    if launch is None:
        return False
    if not sup.tmux.respawn_pane(
        session=target,
        cwd=track.repo,
        command=launch.command,
        env=launch.env,
    ):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
        )
        return False
    if not _supervisor_launch.await_pane(sup=sup, target=target, is_ready=signals.pane_is_codex):
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="respawned pane never became Codex; keeping the ready declaration",
        )
        return False
    fresh_capture = signals.strip_ansi(text=sup.tmux.capture_pane(session=target))
    if resume not in fresh_capture:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=(
                "respawned Codex pane did not show its required resume kick; "
                "keeping the ready declaration"
            ),
        )
        return False
    if not _post_respawn_live_process(sup=sup, track=track, session=session, session_id=session_id):
        _alert_missing_live(sup=sup, track=track, session=session, target=target)
        return False
    return True


def do_codex_restart(*, sup: Supervisor, track: registry.Track, target: str) -> None:
    """Atomic restart of a CODEX track: respawn with ``codex resume <id> "<kick>"``."""
    session = _supervisor_launch.session_of(sup=sup, track=track)
    live = sup.live_codex.get((session, track.topic))
    if live is None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="codex session vanished before restart; keeping the ready declaration",
        )
        return
    session_id = _supervisor_launch.canonical_codex_session_id(value=live.session_id)
    if session_id is None:
        # Fail before respawn: no positional UUID would open the interactive picker.
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message=(
                "codex restart refused: live session has no valid UUID; "
                "keeping the ready declaration"
            ),
        )
        return
    resume = resume_for_track(track=track)
    if resume is None:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=target,
            message="ready cannot respawn: no plan epic recorded",
            condition="restart-plan-epic-missing",
        )
        return
    sup.log(
        message=(
            f"codex restart dispatch {track.repo}::{track.topic} "
            f"(pane {target}; session-id {session_id}; resume {resume!r})"
        )
    )
    if not _respawn_verified(
        sup=sup,
        track=track,
        target=target,
        session=session,
        session_id=session_id,
        resume=resume,
    ):
        return
    # The kick was submitted BY the `codex resume` argument — no separate paste step.
    _supervisor_state.clear_state(
        sup=sup,
        track=track,
        diagnostic_token=signals.STATE_RESTARTED,
        diagnostic_detail="restart completed; consumed ready declaration",
    )
    _ = sup.inject.pop(track_key(repo=track.repo, topic=track.topic), None)
    sup.log(message=f"consumed ready declaration for {track.repo}::{track.topic}")
    sup.log(message=f"restarted (codex) {track.repo}::{track.topic} (pane {target})")
