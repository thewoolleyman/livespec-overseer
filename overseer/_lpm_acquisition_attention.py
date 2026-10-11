"""Deadline-bounded verification attention with capture-destroying failure closure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

__all__: list[str] = [
    "AttentionOutcome",
    "AttentionSession",
    "attention_deadline",
    "resolve_attention",
]


class ArtifactRemoval(Protocol):
    def __call__(self) -> None:
        """Remove the durable attention artifact."""
        ...


class FailureTransition(Protocol):
    def __call__(self, *, reason: str) -> None:
        """Complete the acquisition's terminal failed transition."""
        ...


@dataclass(kw_only=True)
class AttentionSession:
    """The only authority retained while a verification wall is pending."""

    profile_ref: str
    remaining_steps: int
    deadline: float
    captures: list[bytearray] = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class AttentionOutcome:
    """Secret-free wait, resume, or terminal-failure decision."""

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
    remove_artifact: ArtifactRemoval,
    transition_failed: FailureTransition,
) -> AttentionOutcome:
    """Preserve timely authority or destroy it and complete terminal failure."""
    timely = now < session.deadline
    if (status, timely) == ("pending", True):
        return _preserved(action="wait", session=session)

    removed = _remove_artifact(remove_artifact=remove_artifact)
    if (status, timely, removed) == ("resolved", True, True):
        return _preserved(action="resume", session=session)
    return _terminal_failure(session=session, transition_failed=transition_failed)


def _preserved(*, action: str, session: AttentionSession) -> AttentionOutcome:
    return AttentionOutcome(
        action=action,
        profile_ref=session.profile_ref,
        remaining_steps=session.remaining_steps,
    )


def _remove_artifact(*, remove_artifact: ArtifactRemoval) -> bool:
    try:
        remove_artifact()
    except OSError:
        return False
    return True


def _terminal_failure(
    *, session: AttentionSession, transition_failed: FailureTransition
) -> AttentionOutcome:
    for capture in session.captures:
        capture.clear()
    transition_failed(reason="flow-unavailable")
    return AttentionOutcome(action="failed", profile_ref=None, remaining_steps=0)
