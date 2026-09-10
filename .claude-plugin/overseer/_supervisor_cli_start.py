"""The one-shot supervisor `start` command body."""

from __future__ import annotations

import argparse
import os
from typing import Protocol

import _supervisor_assignment
import _supervisor_cli_update
import registry
import signals
import streams
import tmuxio
from _supervisor_core import Supervisor
from _supervisor_dead_track import AmbiguousRuntime, classify_dead_track
from _supervisor_start_cli import StartLaunchMessage, launch_attempt_message

__all__: list[str] = [
    "start_command",
]


class TmuxDeriver(Protocol):
    def __call__(self, *, repo: str, topic: str, allow_reserved: bool = False) -> str | None: ...


class TmuxFactory(Protocol):
    def __call__(self) -> tmuxio.TmuxIO: ...


class SupervisorFactory(Protocol):
    def __call__(self, *, tmux: tmuxio.TmuxIO) -> Supervisor: ...


def _existing_start_track(*, repo: str, topic: str) -> registry.Track | None:
    repo_norm = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=None):
        if registry.norm(repo=track.repo) == repo_norm and track.topic == topic and track.assigned:
            return track
    return None


def _report_launch_failure(
    *,
    io: tmuxio.TmuxIO,
    attempt: StartLaunchMessage,
    repo: str,
    topic: str,
    session: str,
    created_session: bool,
) -> None:
    """Report a launch that never landed, tearing down a session this call created.

    A session `start` created and then failed to launch into is torn down so a retry can
    take the create-then-launch path again rather than inheriting a husk; a session that
    already existed is left exactly as it was found.
    """
    cleanup = "not_created"
    if created_session:
        cleanup = "cleaned" if io.kill_session(session=session) else "leftover_session"
    streams.write_stderr(
        text=(
            f"start FAILED to launch {repo}::{topic} in tmux session {session}; "
            f"reason={attempt.reason or 'launch_failed'} "
            f"session={session} repo={repo} topic={topic} cleanup={cleanup}\n"
        )
    )


def start_command(
    *,
    args: argparse.Namespace,
    derive_tmux_or_refuse: TmuxDeriver,
    tmux_factory: TmuxFactory,
    supervisor_factory: SupervisorFactory,
) -> int:
    """Surface-only, user-initiated launch. The daemon never invokes this.

    Guarded (B8): if the session already runs a LIVE Claude, ``start`` does NOT
    ``respawn-pane -k`` it (that would kill a mid-work session with no interlock —
    the exact "never force-kill mid-work" violation the whole design exists to
    prevent, reachable via a repeated bottom-pane ``start``). It just upserts the
    mapping and reports. ``--force`` is required to actually respawn a live one.

    RUNTIME-DISPATCHED, on evidence, BEFORE anything is created. The track is classified
    by :func:`_supervisor_dead_track.classify_dead_track` ahead of ``new-session`` and
    ahead of any respawn, so an ambiguous runtime is reported to the operator without a
    single tmux mutation — and a track carrying a proven ``codex:<uuid>`` identity
    resumes its own rollout instead of being recreated under the Claude launcher, which
    would replace the Codex session outright.
    """
    repo = os.path.normpath(args.repo)
    topic = args.topic
    existing = _existing_start_track(repo=repo, topic=topic)
    allow_reserved = existing is not None and signals.topic_reserved_for_supervisor(topic=topic)
    session = derive_tmux_or_refuse(repo=repo, topic=topic, allow_reserved=allow_reserved)
    if session is None:
        return 1
    force = getattr(args, "force", False)
    io = tmux_factory()
    sup = supervisor_factory(tmux=io)
    track = existing or _supervisor_assignment.assignment_track(
        repo=repo, topic=topic, session=session
    )
    if io.session_exists(session=session) and not force:
        # Fail CLOSED (RB4): refuse to respawn-kill an existing session unless we
        # POSITIVELY know it is DEAD. Only a bare SHELL proves that — a dead session
        # reports its shell name positively, so demanding proof costs nothing, while an
        # unreadable `pane_current_command` (None) or ANY other program might be live
        # work mid-flight.
        #
        # This asks "is it proven dead?", NOT "is it a live Claude?" (adversarial review,
        # probe-proven, 2026-07-17). The old test was `cmd is None or pane_is_claude(cmd)`,
        # which knew only ONE runtime: a live CODEX pane reports `bun`, failed the
        # Claude test, and was treated exactly like a dead shell — so a bare `start`
        # respawn-KILLED a live Codex TUI and replaced it with a claude one. The guard's
        # own stated purpose was already "fail closed on anything unproven-dead"; it just
        # enumerated the live runtimes instead of the dead one, which does not scale to a
        # second runtime and never did.
        cmd = io.pane_current_command(session=session)
        if not signals.pane_is_shell(pane_current_command=cmd):
            _ = _supervisor_cli_update.upsert_track(track=track)
            streams.write_stdout(
                text=(
                    f"{repo}::{topic}: session {session} already running (or its identity is "
                    f"unreadable) — mapping upserted, NOT respawned. Pass --force to respawn "
                    f"(kills the running session).\n"
                )
            )
            return 0
    runtime = classify_dead_track(track=track, codex_home=sup.codex_home)
    if isinstance(runtime, AmbiguousRuntime):
        streams.write_stderr(
            text=(
                f"start REFUSED for {repo}::{topic}: {runtime.reason}; "
                f"reason=ambiguous_runtime session={session} repo={repo} topic={topic}\n"
            )
        )
        return 1
    created_session = False
    if not io.session_exists(session=session):
        _ = io.new_session(name=session, cwd=repo)
        # Require the EXACT session to exist before launching (Codex re-review #3):
        # a failed `new-session` must not let `_do_launch` respawn a prefix-matched
        # sibling.
        if not io.session_exists(session=session):
            streams.write_stderr(
                text=(
                    f"start FAILED: could not create tmux session {session}; "
                    "reason=session_create_failed "
                    f"session={session} repo={repo} topic={topic}\n"
                )
            )
            return 1
        created_session = True
    attempt = launch_attempt_message(sup=sup, io=io, track=track, session=session, runtime=runtime)
    if attempt.message is None:
        _report_launch_failure(
            io=io,
            attempt=attempt,
            repo=repo,
            topic=topic,
            session=session,
            created_session=created_session,
        )
        return 1
    _ = _supervisor_cli_update.upsert_track(track=track)
    streams.write_stdout(text=f"{attempt.message}\n")
    return 0
