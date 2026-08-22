"""Convergence and exit policy for the foreman runtime loop."""

from __future__ import annotations

from foreman_runtime_document import ForemanDocument

__all__: list[str] = [
    "exit_reason",
    "stable_ticks",
]


def stable_ticks(
    *,
    state: dict[str, object],
    document: ForemanDocument,
    action_taken: bool,
    scheduled_tick: bool,
) -> int:
    if not document.monitored_entities or action_taken:
        return 0
    if state.get("last_fingerprint") != document.fingerprint:
        return 1 if scheduled_tick else 0
    if not scheduled_tick:
        return _int_state(value=state.get("stable_ticks"))
    return _int_state(value=state.get("stable_ticks")) + 1


def exit_reason(
    *,
    tick_generation: int,
    stable_ticks: int,
    document: ForemanDocument,
    hard_tick_budget: int,
    converged_ticks: int,
) -> str | None:
    if tick_generation >= hard_tick_budget:
        return "hard-tick-budget"
    if document.monitored_entities and stable_ticks >= converged_ticks:
        return "converged"
    return None


def _int_state(*, value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
