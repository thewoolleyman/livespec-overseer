"""The exact Herdr payload that records a daemon-confirmed agent session."""

from __future__ import annotations

__all__: list[str] = ["report_agent_session_params"]


def report_agent_session_params(
    *, pane_id: str, source: str, agent_session_id: str
) -> dict[str, object]:
    """Record a Codex thread as the agent session of exactly one pane."""
    return {
        "pane_id": pane_id,
        "source": source,
        "agent": "codex",
        "agent_session_id": agent_session_id,
    }
