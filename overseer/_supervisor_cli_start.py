"""The one-shot supervisor `start` command body."""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from typing import cast

import _supervisor_assignment
import _supervisor_cli_native_start
import _supervisor_cli_start_failures
import _supervisor_cli_update
import herdr_identity
import pane_router
import registry
import signals
import streams
from _supervisor_cli_start_types import (
    NativeCreationCommitter,
    NativeCreator,
    StartContext,
    SupervisorFactory,
    TmuxDeriver,
    TmuxFactory,
)
from _supervisor_dead_track import AmbiguousRuntime, classify_dead_track
from _supervisor_start_cli import launch_attempt_message

__all__: list[str] = [
    "start_command",
]


def _existing_start_track(*, repo: str, topic: str) -> registry.Track | None:
    repo_norm = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=None):
        if registry.norm(repo=track.repo) == repo_norm and track.topic == topic and track.assigned:
            return track
    return None


def _native_source(*, existing: registry.Track | None, owned: str | None) -> str | None:
    if existing is not None:
        value = existing.tmux or ""
        return value if herdr_identity.decode_herdr_target(value=value) is not None else None
    if owned is not None and herdr_identity.decode_herdr_target(value=owned) is not None:
        return owned
    return None


def _start_context(
    *,
    repo: str,
    topic: str,
    existing: registry.Track | None,
    derive_tmux_or_refuse: TmuxDeriver,
    tmux_factory: TmuxFactory,
    supervisor_factory: SupervisorFactory,
) -> StartContext | None:
    native_source = _native_source(
        existing=existing,
        owned=pane_router.current_process_coordinate(),
    )
    allow_reserved = existing is not None and signals.topic_reserved_for_supervisor(topic=topic)
    session = existing.tmux if existing is not None else native_source
    if session is None:
        session = derive_tmux_or_refuse(repo=repo, topic=topic, allow_reserved=allow_reserved)
    if session is None:
        return None
    io = pane_router.default_pane_driver() if native_source is not None else tmux_factory()
    return StartContext(
        io=io,
        sup=supervisor_factory(tmux=io),
        track=existing
        or _supervisor_assignment.assignment_track(repo=repo, topic=topic, session=session),
        session=session,
        native_source=native_source,
        needs_native_creation=native_source is not None
        and (existing is None or not io.session_exists(session=session)),
    )


def _existing_session_handled(*, context: StartContext, force: bool, repo: str, topic: str) -> bool:
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
    if (
        context.needs_native_creation
        or not context.io.session_exists(session=context.session)
        or force
    ):
        return False
    cmd = context.io.pane_current_command(session=context.session)
    if signals.pane_is_shell(pane_current_command=cmd):
        return False
    _ = _supervisor_cli_update.upsert_track(track=context.track)
    streams.write_stdout(
        text=(
            f"{repo}::{topic}: session {context.session} already running (or its identity is "
            "unreadable) — mapping upserted, NOT respawned. Pass --force to respawn "
            "(kills the running session).\n"
        )
    )
    return True


def _created_context(
    *, context: StartContext, existing: registry.Track | None, repo: str, topic: str
) -> StartContext | None:
    if context.needs_native_creation:
        creation = cast(NativeCreator, context.io).create_initial_pane(
            source=cast(str, context.native_source), name=topic, cwd=repo
        )
        if not creation.ok:
            if creation.effect_unknown:
                track = replace(context.track, tmux=creation.target)
                _ = _supervisor_cli_update.upsert_track(
                    track=track,
                    allow_retarget=existing is not None,
                )
            _supervisor_cli_start_failures.report_creation_failure(
                creation=creation, repo=repo, topic=topic
            )
            return None
        track = replace(context.track, tmux=creation.target)
        _ = _supervisor_cli_update.upsert_track(
            track=track,
            allow_retarget=existing is not None,
        )
        if hasattr(context.io, "created_initial_pane_persisted"):
            cast(NativeCreationCommitter, context.io).created_initial_pane_persisted(
                repo=repo,
                topic=topic,
                session=creation.target,
            )
        return replace(context, track=track, session=creation.target, created_session=True)
    if context.io.session_exists(session=context.session):
        return context
    _ = context.io.new_session(name=context.session, cwd=repo)
    if context.io.session_exists(session=context.session):
        return replace(context, created_session=True)
    streams.write_stderr(
        text=(
            f"start FAILED: could not create tmux session {context.session}; "
            "reason=session_create_failed "
            f"session={context.session} repo={repo} topic={topic}\n"
        )
    )
    return None


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
    context = _supervisor_cli_native_start.admitted_start_context(
        context=_start_context(
            repo=repo,
            topic=topic,
            existing=existing,
            derive_tmux_or_refuse=derive_tmux_or_refuse,
            tmux_factory=tmux_factory,
            supervisor_factory=supervisor_factory,
        ),
        repo=repo,
        topic=topic,
    )
    if context is None:
        return 1
    force = getattr(args, "force", False)
    if _existing_session_handled(context=context, force=force, repo=repo, topic=topic):
        return 0
    runtime = classify_dead_track(track=context.track, codex_home=context.sup.codex_home)
    if isinstance(runtime, AmbiguousRuntime):
        streams.write_stderr(
            text=(
                f"start REFUSED for {repo}::{topic}: {runtime.reason}; "
                f"reason=ambiguous_runtime session={context.session} repo={repo} topic={topic}\n"
            )
        )
        return 1
    created = _created_context(context=context, existing=existing, repo=repo, topic=topic)
    if created is None:
        return 1
    attempt = launch_attempt_message(
        sup=created.sup,
        io=created.io,
        track=created.track,
        session=created.session,
        runtime=runtime,
    )
    if attempt.message is None:
        _supervisor_cli_start_failures.report_launch_failure(
            io=created.io,
            attempt=attempt,
            repo=repo,
            topic=topic,
            session=created.session,
            created_session=created.created_session,
        )
        return 1
    _ = _supervisor_cli_update.upsert_track(track=created.track)
    streams.write_stdout(text=f"{attempt.message}\n")
    return 0
