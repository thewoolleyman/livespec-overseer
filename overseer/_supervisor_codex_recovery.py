"""_supervisor_codex_recovery — the VERIFIED Codex arm of deliberate dead-track recovery.

The Codex twin of :func:`_supervisor_recovery.do_launch_result`, and the launcher every
deliberate recovery entry point uses once :func:`_supervisor_dead_track.classify_dead_track`
has established the runtime. It respawns ``codex resume <uuid> "<kick>"`` and then PROVES
the relaunch before reporting success.

**Why proof, not a pane command.** The retired recovery arm returned True as soon as the
pane reported a Codex foreground command. That answers "is a Codex somewhere in this pane",
not "did THIS track's session resume": it cannot tell the target session from a sibling,
the resumed UUID from another rollout, the repository from wherever the pane happens to
sit, or an auto-submitted resume kick from a Codex parked on its session picker. A
deterministic execution returned True with an EMPTY live-Codex map. So the round is judged
only on live process evidence that matches, all four at once, the target tmux session, the
plan topic, the exact session UUID, and the repository cwd — plus the pane going busy,
which is the Codex submit-confirm signal :func:`_supervisor_launch.submit_prompt_result`
already uses (Codex has no ``❯`` box to watch clear).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_initial_process
import _supervisor_launch
import registry
import signals
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX
from _supervisor_launch_profile import CodexLaunchPlan
from _supervisor_prompts import launch_resume

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CODEX_KICK_UNCONFIRMED",
    "CODEX_LIVE_PROCESS_MISSING",
    "CODEX_PANE_NOT_CODEX",
    "CODEX_PANE_UNRESOLVED",
    "CODEX_RESPAWN_FAILED",
    "CODEX_RESUME_PICKER",
    "CodexLaunchResult",
    "codex_launch_reason",
    "codex_launch_result",
]

CODEX_PANE_UNRESOLVED = "codex_pane_unresolved"
CODEX_RESPAWN_FAILED = "codex_respawn_failed"
CODEX_PANE_NOT_CODEX = "codex_pane_never_became_codex"
CODEX_RESUME_PICKER = "codex_resume_picker"
CODEX_LIVE_PROCESS_MISSING = "codex_live_process_missing"
CODEX_KICK_UNCONFIRMED = "codex_resume_kick_unconfirmed"


@dataclass(frozen=True, kw_only=True)
class CodexLaunchResult:
    reason: str | None
    effect_unknown: bool = False


def codex_launch_reason(
    *, sup: Supervisor, track: registry.Track, session: str, session_id: str
) -> str | None:
    """Resume ``session_id`` in ``session`` and verify it. None on success, else a reason.

    ``session`` is the (just-created or existing) session NAME; the pane id is resolved
    from it and every pane op targets that id, so a bare ``-t <name>`` can never
    prefix-match a live sibling. The respawn cwd is ``track.repo``, which matches the
    Codex session's own recorded cwd, so the resume reattaches with no working-dir picker.
    """
    return codex_launch_result(
        sup=sup,
        track=track,
        session=session,
        session_id=session_id,
    ).reason


def codex_launch_result(
    *, sup: Supervisor, track: registry.Track, session: str, session_id: str
) -> CodexLaunchResult:
    """Resume and verify Codex while preserving native launch uncertainty."""
    target = sup.tmux.pane_id(session=session)
    if target is None:
        return CodexLaunchResult(reason=CODEX_PANE_UNRESOLVED)
    launch = _supervisor_launch.codex_launch_plan(
        track=track, session_id=session_id, resume=launch_resume(track=track)
    )
    if not isinstance(launch, CodexLaunchPlan):
        return CodexLaunchResult(reason=launch.message)
    attempt = _supervisor_initial_process.start_initial_process(
        sup=sup,
        track=track,
        target=target,
        launch=launch,
        expected_process="codex",
        failure_reason=CODEX_RESPAWN_FAILED,
    )
    ready = attempt.launched and _supervisor_launch.await_pane(
        sup=sup,
        target=target,
        is_ready=signals.pane_is_codex,
    )
    finished = _supervisor_initial_process.finish_initial_process(
        sup=sup,
        track=track,
        target=target,
        attempt=attempt,
        confirmed=ready,
    )
    if not attempt.launched:
        return CodexLaunchResult(
            reason=finished.reason,
            effect_unknown=finished.effect_unknown,
        )
    if not ready:
        return CodexLaunchResult(
            reason=CODEX_PANE_NOT_CODEX,
            effect_unknown=finished.effect_unknown,
        )
    return CodexLaunchResult(
        reason=_verified_resume(
            sup=sup,
            track=track,
            target=target,
            session=session,
            session_id=session_id,
        )
    )


def _verified_resume(
    *, sup: Supervisor, track: registry.Track, target: str, session: str, session_id: str
) -> str | None:
    """Poll for BOTH proofs, bounded: the exact live process, and the submitted kick.

    Both facts are gathered in one bounded window because they land at different moments —
    the resumed process registers its rollout when it starts, while the auto-submitted kick
    shows as busy once the model answers — and each is latched the first time it is
    observed, so a fast turn cannot be missed between two separate polls. A structured
    picker aborts immediately: a Codex that dropped to its chooser never took the resume
    argument at all, and no amount of waiting changes that.
    """
    kick_confirmed = False
    identity_confirmed = False
    for _ in range(RESTART_POLL_MAX):
        capture = sup.tmux.capture_pane(session=target)
        if signals.is_structured_gate(capture_text=capture):
            return CODEX_RESUME_PICKER
        kick_confirmed = kick_confirmed or signals.is_busy(capture_text=capture)
        sup.refresh_codex_sessions()
        live = sup.live_codex.get((session, track.topic))
        identity_confirmed = identity_confirmed or (
            live is not None
            and live.session_id == session_id
            and signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
        )
        if kick_confirmed and identity_confirmed:
            return None
        sup.sleep(RESTART_POLL_INTERVAL)
    return CODEX_LIVE_PROCESS_MISSING if not identity_confirmed else CODEX_KICK_UNCONFIRMED
