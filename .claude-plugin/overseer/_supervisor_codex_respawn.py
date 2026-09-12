"""Replacing the pane's process with a live, input-accepting fresh Codex session.

The first phase of the fresh-Codex wrap-up restart, split out of
:mod:`_supervisor_codex_fresh` by cohesion: everything between the decision to restart
and a pane that is demonstrably a fresh Codex TUI ready to be typed into — resolving the
launch profile, the atomic ``respawn-pane -k``, waiting for the successor binary, and
refusing a pane that came up on a structured picker.

:func:`alert_fresh_restart` lives here as the whole arm's fail-closed reporting surface.
Every refusal on this arm — in this phase and in the naming/kick/adoption phases the
sequence module runs after it — is reported through it, so each one names the plan
topic, the repository, the tmux session and the PANE (invariant 8: the overseer never
prompts on a track's behalf, so an alert line is the operator's only handover) and each
one leaves the ``ready`` declaration exactly where it was.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_launch
import registry
import signals
from _supervisor_launch_profile import CodexLaunchPlan, codex_fresh_launch_plan
from _supervisor_profile_self_heal import heal_cross_runtime_profile
from _supervisor_statusline_model import (
    restart_blocked_by_statusline_mismatch as statusline_mismatch,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["alert_fresh_restart", "fresh_codex_pane"]


def alert_fresh_restart(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    target: str,
    message: str,
    condition: str,
) -> None:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=message,
        condition=condition,
    )


def _launch_plan(
    *, sup: Supervisor, track: registry.Track, target: str, session: str
) -> CodexLaunchPlan | None:
    launch = codex_fresh_launch_plan(track=track, daemon_restart=True)
    if not isinstance(launch, CodexLaunchPlan):
        # A row whose stored profile names the WRONG runtime refuses here forever: the
        # round is already open, so nothing else re-reads the profile, and every later
        # tick produces this same refusal (95 of them, measured 2026-09-12). Recapture
        # it from the live process first. A heal returns here regardless, because the
        # restart must act on a profile the daemon has OBSERVED rather than on one this
        # pass wrote moments ago; the declaration is kept either way.
        if heal_cross_runtime_profile(sup=sup, track=track, session=session, target=target):
            return None
        alert_fresh_restart(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message=f"{launch.message}; keeping the ready declaration so it retries",
            condition="stale-launch-profile",
        )
        return None
    if statusline_mismatch(sup=sup, track=track, target=target, session=session):
        return None
    return launch


def fresh_codex_pane(*, sup: Supervisor, track: registry.Track, target: str, session: str) -> bool:
    """Respawn the pane onto a brand-new Codex session and wait for it to accept input."""
    launch = _launch_plan(sup=sup, track=track, target=target, session=session)
    if launch is None:
        return False
    if not sup.tmux.respawn_pane(
        session=target,
        cwd=track.repo,
        command=launch.command,
        env=launch.env,
    ):
        alert_fresh_restart(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="restart respawn FAILED; keeping the ready declaration so it retries",
            condition="codex-restart-respawn-failed",
        )
        return False
    if not _supervisor_launch.await_pane(sup=sup, target=target, is_ready=signals.pane_is_codex):
        alert_fresh_restart(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="respawned pane never became Codex; keeping the ready declaration",
            condition="codex-post-respawn-not-ready",
        )
        return False
    if signals.is_structured_gate(capture_text=sup.tmux.capture_pane(session=target)):
        alert_fresh_restart(
            sup=sup,
            track=track,
            session=session,
            target=target,
            message="fresh Codex pane is on a structured picker; keeping the ready declaration",
            condition="codex-fresh-picker-after-restart",
        )
        return False
    return True
