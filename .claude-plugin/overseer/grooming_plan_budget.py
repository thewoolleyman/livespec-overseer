"""Plan-budget resolution for the grooming operation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import jsonio
from foreman_gather_sources import parse_repo_config

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
TERMINAL_WORK_ITEM_STATUSES = frozenset({"closed", "done"})


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


def is_plan_anchor_epic(*, item: Mapping[str, object]) -> bool:
    return is_epic(item=item) and plan_slug(item=item) is not None


def is_top_level_anchor_epic(
    *,
    item: Mapping[str, object],
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> bool:
    return is_plan_anchor_epic(item=item) or is_seat_anchor_epic(
        item=item,
        seat_anchor_epic_ids=seat_anchor_epic_ids,
    )


def is_seat_anchor_epic(
    *,
    item: Mapping[str, object],
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> bool:
    anchors = seat_anchor_epic_ids or frozenset()
    identifier = work_item_id(item=item)
    return is_epic(item=item) and identifier is not None and identifier in anchors


def is_epic(*, item: Mapping[str, object]) -> bool:
    return item.get("issue_type") == "epic" or item.get("type") == "epic"


def work_item_id(*, item: Mapping[str, object]) -> str | None:
    value = item.get("id")
    return value if isinstance(value, str) and value != "" else None


def live_thread_slugs_for_repo(
    *,
    repo: Path,
    work_items: Sequence[Mapping[str, object]],
    extra_slugs: Sequence[str],
) -> tuple[str, ...]:
    slugs: set[str] = set(extra_slugs)
    slugs.update(live_plan_directory_slugs(repo=repo))
    slugs.update(live_plan_anchor_slugs(work_items=work_items))
    return tuple(sorted(slugs))


def live_plan_directory_slugs(*, repo: Path) -> tuple[str, ...]:
    plan_dir = repo / "plan"
    try:
        entries = list(plan_dir.iterdir())
    except OSError:
        return ()
    return tuple(
        sorted(entry.name for entry in entries if entry.is_dir() and entry.name != "archive")
    )


def live_plan_anchor_slugs(*, work_items: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    slugs: set[str] = set()
    for item in work_items:
        status = item.get("status")
        if isinstance(status, str) and status.lower() in TERMINAL_WORK_ITEM_STATUSES:
            continue
        slug = plan_slug(item=item)
        if is_epic(item=item) and slug is not None:
            slugs.add(slug)
    return tuple(sorted(slugs))


def plan_slug(*, item: Mapping[str, object]) -> str | None:
    metadata = jsonio.as_object(value=item.get("metadata"))
    candidates = (
        metadata.get("plan_slug") if metadata is not None else None,
        prefixed_value(text=item.get("notes"), prefix="plan_slug="),
        prefixed_value(text=item.get("spec_commitment_hint"), prefix="plan:"),
    )
    for value in candidates:
        slug = non_blank_text(value=value)
        if slug is not None:
            return slug
    return None


def prefixed_value(*, text: object, prefix: str) -> str | None:
    value = non_blank_text(value=text)
    if value is None:
        return None
    return next(
        (token.removeprefix(prefix) for token in value.split() if token.startswith(prefix)), None
    )


def non_blank_text(*, value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value != "" else None
