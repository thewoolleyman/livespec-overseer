"""Codex-specific evidence and backend reporting for attended relaunches."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import codex_sessions
import herdr_identity
import registry
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX, SUBMIT_MAX_ENTERS
from _supervisor_launch import canonical_codex_session_id

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "codex_rename_wait_bound",
    "confirm_codex_rename",
    "derived_session_name",
    "indexed_codex_thread",
    "report_codex_agent_session",
]

_HERDR_REPORT_SOURCE = "overseer"


def derived_session_name(*, sup: Supervisor, track: registry.Track) -> str:
    """Use the same collision-aware name derivation as normal track adoption."""
    return registry.tmux_id(
        repo=track.repo,
        topic=track.topic,
        colliding=getattr(sup, "colliding_topics", frozenset()),
    )


def indexed_codex_thread(*, name: str, sup: Supervisor) -> str | None:
    """Return the canonical identifier the durable index assigns to this exact name."""
    return canonical_codex_session_id(
        value=codex_sessions.latest_session_for_thread_name(
            thread_name=name, codex_home=sup.codex_home
        )
    )


def codex_rename_wait_bound() -> str:
    """State the finite rename-confirmation bound in operator-facing output."""
    maximum = RESTART_POLL_MAX * RESTART_POLL_INTERVAL
    return f"{RESTART_POLL_MAX} polls at {RESTART_POLL_INTERVAL:g}s (at most {maximum:g}s)"


def confirm_codex_rename(
    *, name: str, prior_thread: str | None, sup: Supervisor, target: str
) -> str | None:
    """Return only a NEW, canonically indexed thread named by this launch's rename."""
    if not sup.tmux.bracketed_paste(session=target, text=f"/rename {name}"):
        return None
    for attempt in range(RESTART_POLL_MAX):
        if attempt < SUBMIT_MAX_ENTERS:
            _ = sup.tmux.send_keys(session=target, keys="Enter")
        sup.sleep(RESTART_POLL_INTERVAL)
        indexed = indexed_codex_thread(name=name, sup=sup)
        if indexed is not None and indexed != prior_thread:
            return indexed
    return None


def report_codex_agent_session(*, target: str, thread_id: str) -> bool:
    """Report a confirmed thread only to its exact Herdr pane; tmux cannot accept one."""
    decoded = herdr_identity.decode_target(value=target)
    if decoded.herdr is None:
        return True
    completed = subprocess.run(  # noqa: S603 -- fixed executable and argument positions
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
    )
    return completed.returncode == 0
