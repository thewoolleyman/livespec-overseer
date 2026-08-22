"""Plan-budget resolution for the grooming operation."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import jsonio
from foreman_gather_sources import parse_repo_config
from grooming_plan_threads import (
    TERMINAL_WORK_ITEM_STATUSES,
    is_top_level_anchor_epic,
    live_thread_slugs_for_repo,
    reclaimable_live_thread_slugs,
)

__all__: list[str] = [
    "DEFAULT_ITEMS_PER_PLAN",
    "DEFAULT_MAX_PLANS",
    "DEFAULT_MIN_PLANS",
    "TERMINAL_WORK_ITEM_STATUSES",
    "PlanBudgetResolution",
    "is_top_level_anchor_epic",
    "resolve_plan_budget",
]

DEFAULT_ITEMS_PER_PLAN = 12
DEFAULT_MIN_PLANS = 2
DEFAULT_MAX_PLANS = 20


@dataclass(frozen=True, kw_only=True)
class PlanBudgetResolution:
    path: Literal["explicit", "auto"]
    governing_path: Literal["explicit", "population-derived", "min-clamped", "max-clamped"]
    budget: int
    new_thread_allowance: int
    drainable_population: int
    proposed_changes_count: int
    work_item_count: int
    live_thread_count: int
    live_thread_slugs: tuple[str, ...]
    reclaimable_live_thread_count: int
    reclaimable_live_thread_slugs: tuple[str, ...]
    raw_auto_budget: int
    items_per_plan: int
    min_plans: int
    max_plans: int
    explicit_plan_budget: int | None


def resolve_plan_budget(
    *,
    repo: str | Path,
    work_items: Sequence[Mapping[str, object]] = (),
    proposed_changes_count: int | None = None,
    live_plan_slugs: Sequence[str] = (),
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> PlanBudgetResolution:
    root = Path(repo)
    config = parse_repo_config(repo=root) or {}
    grooming = jsonio.as_object(value=config.get("grooming")) or {}
    items_per_plan = positive_int(value=grooming.get("items_per_plan")) or DEFAULT_ITEMS_PER_PLAN
    min_plans = positive_int(value=grooming.get("min_plans")) or DEFAULT_MIN_PLANS
    max_plans = positive_int(value=grooming.get("max_plans")) or DEFAULT_MAX_PLANS
    proposals = (
        count_pending_proposed_changes(repo=root, config=config)
        if proposed_changes_count is None
        else proposed_changes_count
    )
    work_item_count = count_drainable_work_items(
        work_items=work_items,
        seat_anchor_epic_ids=seat_anchor_epic_ids,
    )
    drainable_population = proposals + work_item_count
    raw_auto_budget = ceil_div(numerator=drainable_population, denominator=items_per_plan)
    explicit_plan_budget = positive_int(value=grooming.get("plan_budget"))
    governing_path = resolve_governing_path(
        explicit_plan_budget=explicit_plan_budget,
        raw_auto_budget=raw_auto_budget,
        min_plans=min_plans,
        max_plans=max_plans,
    )
    budget = budget_for_governing_path(
        governing_path=governing_path,
        explicit_plan_budget=explicit_plan_budget,
        raw_auto_budget=raw_auto_budget,
        min_plans=min_plans,
        max_plans=max_plans,
    )
    live_slugs = live_thread_slugs_for_repo(
        repo=root,
        work_items=work_items,
        extra_slugs=live_plan_slugs,
    )
    live_thread_count = len(live_slugs)
    reclaimable_slugs = reclaimable_live_thread_slugs(
        live_slugs=live_slugs,
        work_items=work_items,
    )
    return PlanBudgetResolution(
        path="explicit" if explicit_plan_budget is not None else "auto",
        governing_path=governing_path,
        budget=budget,
        new_thread_allowance=max(0, budget - live_thread_count),
        drainable_population=drainable_population,
        proposed_changes_count=proposals,
        work_item_count=work_item_count,
        live_thread_count=live_thread_count,
        live_thread_slugs=live_slugs,
        reclaimable_live_thread_count=len(reclaimable_slugs),
        reclaimable_live_thread_slugs=reclaimable_slugs,
        raw_auto_budget=raw_auto_budget,
        items_per_plan=items_per_plan,
        min_plans=min_plans,
        max_plans=max_plans,
        explicit_plan_budget=explicit_plan_budget,
    )


def resolve_governing_path(
    *,
    explicit_plan_budget: int | None,
    raw_auto_budget: int,
    min_plans: int,
    max_plans: int,
) -> Literal["explicit", "population-derived", "min-clamped", "max-clamped"]:
    if explicit_plan_budget is not None:
        return "explicit"
    if raw_auto_budget < min_plans:
        return "min-clamped"
    if raw_auto_budget > max_plans:
        return "max-clamped"
    return "population-derived"


def budget_for_governing_path(
    *,
    governing_path: Literal["explicit", "population-derived", "min-clamped", "max-clamped"],
    explicit_plan_budget: int | None,
    raw_auto_budget: int,
    min_plans: int,
    max_plans: int,
) -> int:
    if governing_path == "explicit":
        return explicit_plan_budget or raw_auto_budget
    if governing_path == "min-clamped":
        return min_plans
    if governing_path == "max-clamped":
        return max_plans
    return raw_auto_budget


def positive_int(*, value: object) -> int | None:
    return value if type(value) is int and value > 0 else None


def ceil_div(*, numerator: int, denominator: int) -> int:
    return (max(0, numerator) + denominator - 1) // denominator


def count_pending_proposed_changes(*, repo: Path, config: Mapping[str, object]) -> int:
    spec_root = config.get("spec_root")
    spec_dir = spec_root if isinstance(spec_root, str) and spec_root else "SPECIFICATION"
    proposed_dir = repo / spec_dir / "proposed_changes"
    entries = list(proposed_dir.glob("*"))
    return sum(1 for entry in entries if entry.is_file() and entry.name != "README.md")


def count_drainable_work_items(
    *,
    work_items: Sequence[Mapping[str, object]],
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> int:
    anchors = seat_anchor_epic_ids or frozenset()
    return sum(
        1 for item in work_items if work_item_is_drainable(item=item, seat_anchor_epic_ids=anchors)
    )


def work_item_is_drainable(
    *,
    item: Mapping[str, object],
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> bool:
    status = item.get("status")
    if isinstance(status, str) and status.lower() in TERMINAL_WORK_ITEM_STATUSES:
        return False
    return not is_top_level_anchor_epic(
        item=item,
        seat_anchor_epic_ids=seat_anchor_epic_ids,
    )
