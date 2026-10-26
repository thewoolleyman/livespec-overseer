"""The active-evaluation result shared by the evaluator's branch helpers."""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = ["ActiveDecision"]


@dataclass(frozen=True, kw_only=True)
class ActiveDecision:
    """The outcome one pre-idle active-evaluation branch publishes."""

    status: str
    note: str | None
    ready: bool
    blocked: str | None
    blocked_age: float | None
    blocked_age_label: str | None
    active_conditions: set[str]
