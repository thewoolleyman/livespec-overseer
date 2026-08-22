"""Durable per-tick state for the foreman plan roster."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import jsonio
from foreman_runtime_state import atomic_json, read_json_object, runtime_dir

__all__: list[str] = [
    "ROSTER_STATE_FILE",
    "mark_roster_tick",
    "roster_state_path",
]

ROSTER_STATE_FILE = "plan-roster-state.json"
SCHEMA_VERSION = 1
MAX_EMITTED_TICK_IDENTITIES = 256


def roster_state_path(*, repo: Path) -> Path:
    return runtime_dir(repo=repo) / ROSTER_STATE_FILE


def _emitted_tick_identities(*, state: dict[str, object]) -> list[str]:
    raw = jsonio.as_list(value=state.get("emitted_tick_identities"))
    if raw is None:
        return []
    return [item for item in raw if isinstance(item, str) and item]


def _plan_counts(*, state: dict[str, object]) -> dict[str, int]:
    raw_plans = jsonio.as_object(value=state.get("plans"))
    if raw_plans is None:
        return {}
    counts: dict[str, int] = {}
    for plan, raw_entry in raw_plans.items():
        entry = jsonio.as_object(value=raw_entry) or {"consecutive_unactioned_ticks": 0}
        counts[plan] = cast(int, entry.get("consecutive_unactioned_ticks", 0))
    return counts


def _payload(*, emitted: list[str], counts: dict[str, int]) -> dict[str, object]:
    return {
        "emitted_tick_identities": emitted[-MAX_EMITTED_TICK_IDENTITIES:],
        "plans": {
            plan: {"consecutive_unactioned_ticks": count} for plan, count in sorted(counts.items())
        },
        "schema_version": SCHEMA_VERSION,
    }


def mark_roster_tick(
    *,
    repo: Path,
    plan_names: list[str],
    tick_identity: str,
    actioned_plan: str | None,
) -> dict[str, int] | None:
    state = read_json_object(path=roster_state_path(repo=repo))
    emitted = _emitted_tick_identities(state=state)
    if tick_identity in emitted:
        return None
    current = _plan_counts(state=state)
    active_plans = set(plan_names)
    counts = {plan: 0 if plan == actioned_plan else current.get(plan, 0) + 1 for plan in plan_names}
    emitted.append(tick_identity)
    atomic_json(
        path=roster_state_path(repo=repo),
        payload=_payload(
            emitted=emitted,
            counts={plan: count for plan, count in counts.items() if plan in active_plans},
        ),
    )
    return counts
