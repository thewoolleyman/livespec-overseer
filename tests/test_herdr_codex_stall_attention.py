"""Operator recovery instructions for stalled Codex Herdr replacements."""

from __future__ import annotations

from types import SimpleNamespace

import _supervisor_herdr_stall


def test_codex_launch_or_resume_stall_names_the_pane_and_manual_recovery() -> None:
    """A terminal retry stall must leave the operator exact next steps."""
    assert hasattr(_supervisor_herdr_stall, "stall_attention_message")

    message = _supervisor_herdr_stall.stall_attention_message(
        track=SimpleNamespace(repo="/repo", topic="topic"),
        target="w2:p1",
        phase="resume-attempted",
        runtime="codex",
        reason="pending Codex resume Enter retry budget is exhausted",
    )

    assert message == (
        "herdr replacement stalled for /repo::topic at pane w2:p1; "
        "phase resume-attempted: pending Codex resume Enter retry budget is exhausted. "
        "Manual steps: /rename topic, then submit the durable resume line."
    )
