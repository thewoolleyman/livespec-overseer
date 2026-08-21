"""Command construction for bounded foreman work-item sessions."""

from __future__ import annotations

from pathlib import Path

import jsonio
from foreman_act_commands import resume_command_from_payload

__all__: list[str] = [
    "resume_command",
    "start_command",
]


def start_command(*, repo: Path, session_name: str, handoff: Path) -> list[str]:
    prompt = f"read {handoff} and complete this bounded one-shot work-item session"
    return [
        "tmux",
        "new-session",
        "-d",
        "-s",
        session_name,
        "-c",
        str(repo),
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        prompt,
    ]


def resume_command(*, proposal: dict[str, object], handoff: Path) -> list[str] | None:
    classifier = jsonio.as_object(value=proposal.get("classifier")) or {}
    resume = jsonio.as_object(value=classifier.get("resume"))
    if resume is None:
        return None
    return resume_command_from_payload(
        payload={**resume, "handoff_path": str(handoff), "topic": str(proposal["topic"])}
    )
