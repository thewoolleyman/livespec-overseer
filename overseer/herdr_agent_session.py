"""The exact Herdr payload that records a daemon-confirmed agent session."""

from __future__ import annotations

import herdr_protocol
import herdr_write_calls

__all__: list[str] = ["report_agent_session"]


def report_agent_session(
    *, pane_id: str, source: str, agent_session_id: str
) -> tuple[str, dict[str, object], herdr_protocol.ReplyExpectation]:
    """Build the native report for exactly one pane and daemon-confirmed Codex thread."""
    return (
        herdr_protocol.METHOD_PANE_REPORT_AGENT_SESSION,
        {
            "pane_id": pane_id,
            "source": source,
            "agent": "codex",
            "agent_session_id": agent_session_id,
        },
        herdr_write_calls.EXPECT_OK,
    )
