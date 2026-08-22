"""Foreman runtime writes for non-blocking human-decision escalation."""

from __future__ import annotations

from pathlib import Path

from _supervisor_foreman_escalation import escalation_path
from foreman_runtime_identity import canonical_session_name
from foreman_runtime_state import atomic_json

__all__: list[str] = ["record_blocking_prompt_escalation"]

_BLOCKING_PROMPT_REASON = (
    "foreman tick ended with a blocking prompt; the decision must stay on "
    "the non-blocking attention surface so the loop cadence can continue"
)


def record_blocking_prompt_escalation(*, repo: Path) -> None:
    topic = canonical_session_name(repo=repo)
    atomic_json(
        path=escalation_path(repo=str(repo), topic=topic),
        payload={"reason": _BLOCKING_PROMPT_REASON},
    )
