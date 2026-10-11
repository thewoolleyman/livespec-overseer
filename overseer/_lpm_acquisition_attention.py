"""Deadline-bounded verification attention with capture-destroying failure closure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

__all__: list[str] = [
    "AttentionOutcome",
    "AttentionSession",
    "attention_deadline",
    "resolve_attention",
]


@dataclass(kw_only=True)
class AttentionSession:
    """The only authority retained while a CAPTCHA or two-factor wall is pending."""

    profile_ref: str
    remaining_steps: int
    deadline: float
    captures: list[bytearray] = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class AttentionOutcome:
    """Secret-free resume or terminal-failure decision."""

    action: str
    profile_ref: str | None
    remaining_steps: int


def attention_deadline(*, raised_at: float, wait_seconds: int, worker_deadline: float) -> float:
    """Clamp operator attention to the acquisition worker's own deadline."""
    return min(raised_at + wait_seconds, worker_deadline)


def resolve_attention(
    *,
    session: AttentionSession,
    status: str,
    now: float,
    remove_artifact: Callable[[], None],
    transition_failed: Callable[[str], None],
) -> AttentionOutcome:
    """Resume a timely resolution or destroy all authority on give-up or expiry."""
    remove_artifact()
    if status == "resolved" and now < session.deadline:
        return AttentionOutcome(
            action="resume",
            profile_ref=session.profile_ref,
            remaining_steps=session.remaining_steps,
        )
    for capture in session.captures:
        capture.clear()
    transition_failed("flow-unavailable")
    return AttentionOutcome(action="failed", profile_ref=None, remaining_steps=0)
