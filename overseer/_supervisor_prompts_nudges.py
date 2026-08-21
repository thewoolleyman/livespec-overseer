"""Standalone supervisor prompt nudges."""

from __future__ import annotations

import signals

__all__: list[str] = [
    "charter_authorized_unblock_nudge_message",
    "pair_stall_nudge_message",
]

_CHARTER_AUTHORIZED_UNBLOCK_NUDGE = """\
Your supervisor charter already says:

A wait is not a question. A mechanical unblock is not a question.
If the SUPERVISOR can perform the unblock, PERFORM IT.

The overseer is not choosing from this picker and will not answer it for you. Re-read
the pending picker, perform only charter-authorized mechanical unblocks yourself, and
declare `blocked: <reason>` only when the unblock genuinely requires a human decision."""


def charter_authorized_unblock_nudge_message() -> str:
    """Reminder pasted into a stalled supervisor picker without submitting an answer."""
    return _CHARTER_AUTHORIZED_UNBLOCK_NUDGE


def pair_stall_nudge_message(
    *,
    repo: str,
    topic: str,
    worker_session: str,
    worker_pane: str | None,
    stalled_seconds: float,
    plan_state: str,
) -> str:
    """Nudge a stalled supervisor/worker pair through the supervisor pane."""
    state_file = signals.state_path(repo=repo, topic=signals.supervisor_entity_topic(topic=topic))
    duration = f"{stalled_seconds / 3600:.1f}h"
    return f"""\
Your worker/supervisor pair has shown no progress for {duration}.

You own direction for this pair. Resume driving the worker now, or if the pair is
actually waiting on a human question, surface that explicitly by declaring it out-of-band:
    echo 'blocked: <one-line reason>' > {state_file}

Worker coordinates: tmux session '{worker_session}', pane {worker_pane}.
Worker plan state: {plan_state}"""
