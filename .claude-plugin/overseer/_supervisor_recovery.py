"""_supervisor_recovery — startup-only revival of a mapped-but-dead session.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This runs ONCE at daemon startup and NEVER per tick: the daemon is a
surface-only watcher, so re-launching a session the store maps but tmux no longer has
is a deliberate startup act, not something a tick may decide.

Sits on top of :mod:`_supervisor_launch` — it decides WHICH tracks to revive and
reports what it did, while the launch primitives carry each revival out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_launch
import codex_sessions
import registry
import signals
from _supervisor_launch_profile import ClaudeLaunchPlan, CodexLaunchPlan, rendered_statusline_model
from _supervisor_prompts import launch_resume

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "LaunchResult",
    "do_codex_launch",
    "do_launch",
    "do_launch_result",
    "recover_codex_track",
    "recover_missing_sessions",
]


@dataclass(frozen=True, kw_only=True)
class LaunchResult:
    launched: bool
    reason: str | None = None


def recover_missing_sessions(*, sup: Supervisor) -> list[str]:
    """Recreate any mapped session that is not currently live (design).

    Run ONCE at daemon startup: a fresh overseer reads the mapping, and for
    each row whose mapped session (``_session_of``: the row's stored ``tmux``, or
    the derived bare-topic / collision name) is gone, recreates it. Not a
    per-tick action (a session the user deliberately kills should not be revived
    every 10s). Returns the recovered names.

    RUNTIME-DISPATCHED (defect #5, 2026-07-18). A dead codex process is absent from the
    live ``self.live_codex`` map (there is no rollout fd at cold start), so the runtime is
    derived from the PERSISTENT codex index instead — which SURVIVES the session's death.
    If the track's TOPIC names a session in ``session_index.jsonl``
    (:func:`codex_sessions.latest_session_for_thread_name`), the track is CODEX and is
    recovered by :meth:`_recover_codex_track` — ``codex resume <id>`` reattaches the SAME
    rollout (option c) when it still exists on disk, else a skip+surface (option b), NEVER
    a mis-recreation as Claude. Otherwise the track is Claude and is recreated with
    ``claude --dangerously-skip-permissions -n <topic>`` (:meth:`_launch_command`) + a
    resume-line paste. Either way the ``session_exists`` gate means only a genuinely
    ABSENT session is recreated, so no live session is ever killed.
    """
    recovered: list[str] = []
    for track in registry.read_valid_mapping(store_path=sup.store_path):
        session = _supervisor_launch.session_of(sup=sup, track=track)
        if sup.tmux.session_exists(session=session):
            continue
        # Runtime dispatch: a topic named in the persistent codex index is a CODEX track.
        # The index survives the session's death, so it is the ONLY runtime signal at cold
        # start. `_recover_codex_track` resumes the same rollout (option c) or skips+surfaces
        # (option b) — it NEVER falls through to the Claude path below (rollout-orphaning).
        codex_id = codex_sessions.latest_session_for_thread_name(
            thread_name=track.topic, codex_home=sup.codex_home
        )
        if codex_id is not None:
            name = recover_codex_track(sup=sup, track=track, session=session, session_id=codex_id)
            if name is not None:
                recovered.append(name)
            continue
        _ = sup.tmux.new_session(name=session, cwd=track.repo)
        # Require the EXACT session to now exist before launching (Codex
        # re-review #3): if `new-session` failed, `_do_launch`'s pane-id
        # resolution + `respawn-pane` would target the bare name, which could
        # prefix-match a live sibling and replace IT. Fail-soft: surface + skip.
        if not sup.tmux.session_exists(session=session):
            sup.surface(
                message=f"reboot-recovery: new-session did not create {session} "
                f"for {track.repo}::{track.topic}; skipping"
            )
            continue
        if do_launch(sup=sup, track=track, session=session):
            recovered.append(session)
            sup.log(message=f"reboot-recovery recreated {session} for {track.repo}::{track.topic}")
        else:
            sup.surface(
                message=f"reboot-recovery FAILED to launch {session} "
                f"for {track.repo}::{track.topic}"
            )
    return recovered


def recover_codex_track(
    *, sup: Supervisor, track: registry.Track, session: str, session_id: str
) -> str | None:
    """Reboot-recover a CODEX track (defect #5): resume the SAME rollout, or skip+surface.

    **Option (c) — resume.** If the session's rollout still exists on disk
    (:func:`codex_sessions.rollout_exists`), create the tmux session and respawn it with
    ``codex resume --dangerously-bypass-approvals-and-sandbox <id> "<kick>"``
    (:meth:`_do_codex_launch`). ``codex resume`` reattaches the SAME conversation and
    preserves its ``thread_name``, so the daemon re-adopts the track on the next tick —
    parity-or-better continuity vs. the Claude path's fresh-session-plus-handoff (verified
    live 2026-07-18: a 26-day-old session reattached, thread_name intact, and — because the
    respawn cwd is ``track.repo``, matching the session's recorded cwd — with no working-dir
    picker).

    **Option (b) — skip + surface.** If the rollout is GONE, ``codex resume`` cannot
    reattach, so recovery SKIPS the track and surfaces it for the operator, NEVER
    mis-recreating it as Claude (which would orphan the rollout). A relaunched codex is
    re-adopted automatically.

    Returns the recovered session name, or None on skip/failure (mirroring the Claude
    path's ``session_exists``/launch gates).
    """
    if not codex_sessions.rollout_exists(session_id=session_id, codex_home=sup.codex_home):
        sup.surface(
            message=f"reboot-recovery: codex track {track.repo}::{track.topic} "
            f"was down at boot and "
            f"its rollout is gone (session {session_id}); relaunch it and it will re-adopt"
        )
        return None
    _ = sup.tmux.new_session(name=session, cwd=track.repo)
    if not sup.tmux.session_exists(session=session):
        sup.surface(
            message=f"reboot-recovery: new-session did not create {session} "
            f"for {track.repo}::{track.topic}; skipping"
        )
        return None
    if do_codex_launch(sup=sup, track=track, session=session, session_id=session_id):
        sup.log(
            message=f"reboot-recovery resumed codex {session} for {track.repo}::{track.topic} "
            f"(session {session_id})"
        )
        return session
    sup.surface(
        message=f"reboot-recovery FAILED to resume codex {session} "
        f"for {track.repo}::{track.topic}"
    )
    return None


def do_codex_launch(
    *, sup: Supervisor, track: registry.Track, session: str, session_id: str
) -> bool:
    """Respawn ``session`` with ``codex resume <id> "<kick>"`` and await a live codex pane.

    The codex twin of :meth:`_do_launch`, and SIMPLER: ``codex resume`` takes the kick as
    its PROMPT argument and AUTO-SUBMITS it (verified live 2026-07-17), so there is no
    separate resume-line paste. ``session`` is the just-created session NAME; the pane id
    is resolved from it and every pane op targets that id (RB3). The respawn cwd is
    ``track.repo`` — which matches the codex session's recorded cwd — so ``codex resume``
    reattaches directly. Returns True iff respawn succeeded and the pane became a live
    codex TUI (a failed respawn / non-codex pane surfaces via the caller).
    """
    target = sup.tmux.pane_id(session=session)
    if target is None:
        return False
    resume = launch_resume(track=track)
    launch = _supervisor_launch.codex_launch_plan(
        track=track,
        session_id=session_id,
        resume=resume,
    )
    if not isinstance(launch, CodexLaunchPlan):
        sup.surface(message=f"reboot-recovery: {launch.message}; skipping")
        return False
    if not sup.tmux.respawn_pane(
        session=target,
        cwd=track.repo,
        command=launch.command,
        env=launch.env,
    ):
        return False
    return _supervisor_launch.await_pane(sup=sup, target=target, is_ready=signals.pane_is_codex)


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
