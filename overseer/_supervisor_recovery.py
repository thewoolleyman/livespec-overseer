"""_supervisor_recovery — deliberate revival of a mapped-but-dead session.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This never runs per tick: the daemon is a surface-only watcher, so re-launching
a session the store maps but tmux no longer has is a deliberate act, not something a
tick may decide.

Sits on top of :mod:`_supervisor_dead_track` (WHICH runtime the dead track is) and the
launch primitives in :mod:`_supervisor_launch` / :mod:`_supervisor_codex_recovery` (how
that runtime is brought back and proven). The operator `start` surface composes the same
two through :func:`dead_track_launch_result`, so both deliberate entry points share one
classifier and one verified launcher rather than two that can drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_codex_recovery
import _supervisor_launch
import registry
import signals
from _supervisor_dead_track import (
    AmbiguousRuntime,
    CodexRuntime,
    LaunchableRuntime,
    classify_dead_track,
)
from _supervisor_launch_profile import ClaudeLaunchPlan, rendered_statusline_model
from _supervisor_prompts import launch_resume

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "LaunchResult",
    "dead_track_launch_result",
    "do_codex_launch",
    "do_launch",
    "do_launch_result",
    "recover_missing_sessions",
]


@dataclass(frozen=True, kw_only=True)
class LaunchResult:
    launched: bool
    reason: str | None = None


def dead_track_launch_result(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    runtime: LaunchableRuntime,
    start: bool = False,
) -> LaunchResult:
    """Launch ``track`` in ``session`` as the runtime the classifier established.

    THE dispatch point for every deliberate dead-track relaunch. A Codex track resumes
    its own rollout through the verified Codex launcher and is reported launched only
    once that verification passes; a Claude track keeps its existing launch path
    byte-for-byte, ``start`` semantics included.
    """
    if isinstance(runtime, CodexRuntime):
        reason = _supervisor_codex_recovery.codex_launch_reason(
            sup=sup, track=track, session=session, session_id=runtime.session_id
        )
        return LaunchResult(launched=reason is None, reason=reason)
    return do_launch_result(sup=sup, track=track, session=session, start=start)


def recover_missing_sessions(*, sup: Supervisor) -> list[str]:
    """Recreate any mapped session that is not currently live (design).

    Reads the mapping, and for each row whose mapped session (:func:`session_of`: the
    row's stored ``tmux``, or the derived bare-topic / collision name) is gone, revives
    it as the runtime :func:`_supervisor_dead_track.classify_dead_track` establishes.
    Returns the recovered names. Not a per-tick action (a session the user deliberately
    kills must not be revived every 10s); the shipped daemon does not call it at all.

    RUNTIME-DISPATCHED, on EVIDENCE. A dead Codex process is absent from the live
    ``self.live_codex`` map (there is no rollout fd at cold start), so the runtime comes
    from the identity the daemon recorded while it WAS alive, corroborated against the
    persisted index. A track whose runtime is ambiguous — a stale same-topic namesake, a
    pruned rollout, an identifier the index maps elsewhere — is SURFACED and left alone:
    no session is created and nothing is launched, so a Codex track can never be
    mis-recreated as Claude (rollout-orphaning) nor a Claude track ``codex resume``-d.
    The ``session_exists`` gate still means only a genuinely ABSENT session is recreated,
    so no live session is ever killed.
    """
    recovered: list[str] = []
    for track in registry.read_valid_mapping(store_path=sup.store_path):
        session = _supervisor_launch.session_of(sup=sup, track=track)
        if sup.tmux.session_exists(session=session):
            continue
        runtime = classify_dead_track(track=track, codex_home=sup.codex_home)
        if isinstance(runtime, AmbiguousRuntime):
            sup.surface(
                message=f"reboot-recovery: NOT launching {track.repo}::{track.topic} — "
                f"ambiguous runtime: {runtime.reason}"
            )
            continue
        name = _revive(sup=sup, track=track, session=session, runtime=runtime)
        if name is not None:
            recovered.append(name)
    return recovered


def _revive(
    *, sup: Supervisor, track: registry.Track, session: str, runtime: LaunchableRuntime
) -> str | None:
    """Create the exact session and launch the classified runtime into it, or surface.

    Require the EXACT session to exist before launching (Codex re-review #3): if
    ``new-session`` failed, the launcher's pane-id resolution + ``respawn-pane`` would
    target the bare name, which could prefix-match a live sibling and replace IT.
    Fail-soft: surface + skip.
    """
    verb = "resumed codex" if isinstance(runtime, CodexRuntime) else "recreated"
    failed_verb = "resume codex" if isinstance(runtime, CodexRuntime) else "launch"
    _ = sup.tmux.new_session(name=session, cwd=track.repo)
    if not sup.tmux.session_exists(session=session):
        sup.surface(
            message=f"reboot-recovery: new-session did not create {session} "
            f"for {track.repo}::{track.topic}; skipping"
        )
        return None
    result = dead_track_launch_result(sup=sup, track=track, session=session, runtime=runtime)
    if not result.launched:
        sup.surface(
            message=f"reboot-recovery FAILED to {failed_verb} {session} "
            f"for {track.repo}::{track.topic}; reason={result.reason}"
        )
        return None
    sup.log(message=f"reboot-recovery {verb} {session} for {track.repo}::{track.topic}")
    return session


def do_codex_launch(
    *, sup: Supervisor, track: registry.Track, session: str, session_id: str
) -> bool:
    """See :func:`_supervisor_codex_recovery.codex_launch_reason` — True iff it verified."""
    return (
        _supervisor_codex_recovery.codex_launch_reason(
            sup=sup, track=track, session=session, session_id=session_id
        )
        is None
    )


def do_launch(*, sup: Supervisor, track: registry.Track, session: str, start: bool = False) -> bool:
    """Launch ``claude --dangerously-skip-permissions -n <topic>`` and paste the resume line.

    ``session`` is the (just-created or existing) session NAME; the pane id is
    resolved from it and every pane op targets that id (RB3). Returns True iff
    respawn succeeded, the pane became a live Claude, and the resume line
    submitted — so callers (`recover`, `start`) can surface a failure rather
    than silently claim a launch happened (B5).
    """
    return do_launch_result(sup=sup, track=track, session=session, start=start).launched


def do_launch_result(
    *, sup: Supervisor, track: registry.Track, session: str, start: bool = False
) -> LaunchResult:
    result = LaunchResult(launched=False, reason="claude_launch_failed")
    target = sup.tmux.pane_id(session=session)
    if target is not None:
        launch = _supervisor_launch.claude_launch_plan(track=track, start=start)
        if not isinstance(launch, ClaudeLaunchPlan):
            sup.surface(message=f"reboot-recovery: {launch.message}; skipping")
            result = LaunchResult(launched=False, reason=launch.message)
        elif sup.tmux.respawn_pane(
            session=target,
            cwd=track.repo,
            command=launch.command,
            env=launch.env,
        ) and _supervisor_launch.await_pane(
            sup=sup, target=target, is_ready=signals.pane_is_claude
        ):
            _ = _supervisor_launch.await_input_box(sup=sup, target=target)
            if start:
                registry.record_launch_statusline_baseline(
                    repo=track.repo,
                    topic=track.topic,
                    model=rendered_statusline_model(capture=sup.tmux.capture_pane(session=target)),
                    stamp_path=sup.stamp_path,
                )
            submitted = _supervisor_launch.submit_prompt_result(
                sup=sup, target=target, text=launch_resume(track=track)
            )
            if submitted.submitted:
                result = LaunchResult(launched=True)
            elif submitted.paste_failed:
                result = LaunchResult(launched=False, reason="resume_submit_failed")
            else:
                result = LaunchResult(launched=True, reason="resume_submit_unverified")
    return result
