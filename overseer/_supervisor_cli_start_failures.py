"""Exact-resource failure handling for the deliberate-start surface."""

from __future__ import annotations

from typing import cast

import herdr_identity
import streams
from _supervisor_cli_start_types import NativeCleaner, NativeMutation
from _supervisor_start_cli import StartLaunchMessage
from tmuxio_protocols import PaneDriver

__all__: list[str] = [
    "report_creation_failure",
    "report_launch_failure",
]


def report_creation_failure(*, creation: NativeMutation, repo: str, topic: str) -> None:
    """Name the exact native target whose creation was refused."""
    streams.write_stderr(
        text=(
            f"start FAILED to create Herdr pane for {repo}::{topic}; "
            f"reason={creation.error or 'pane_create_failed'} backend=herdr "
            f"target={creation.target}\n"
        )
    )


def _cleanup_native(*, io: PaneDriver, session: str) -> bool:
    return cast(NativeCleaner, io).cleanup_initial_pane(session=session)


def _cleanup_tmux(*, io: PaneDriver, session: str) -> bool:
    return io.kill_session(session=session)


def _cleanup(*, io: PaneDriver, session: str, native: bool, created_session: bool) -> str:
    if not created_session:
        return "not_created"
    cleaned = {True: _cleanup_native, False: _cleanup_tmux}[native](io=io, session=session)
    return "cleaned" if cleaned else "leftover_session"


def report_launch_failure(
    *,
    io: PaneDriver,
    attempt: StartLaunchMessage,
    repo: str,
    topic: str,
    session: str,
    created_session: bool,
) -> None:
    """Report a failed launch and clean only a resource this invocation created."""
    native = herdr_identity.decode_herdr_target(value=session) is not None
    cleanup = _cleanup(
        io=io,
        session=session,
        native=native,
        created_session=created_session,
    )
    location = {
        True: f"in herdr pane {session}; backend=herdr target={session}",
        False: f"in tmux session {session}; session={session}",
    }[native]
    streams.write_stderr(
        text=(
            f"start FAILED to launch {repo}::{topic} {location}; "
            f"reason={attempt.reason or 'launch_failed'} "
            f"repo={repo} topic={topic} cleanup={cleanup}\n"
        )
    )
