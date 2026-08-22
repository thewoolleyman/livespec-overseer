"""Live plan-thread classification for grooming budget resolution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import cast

import jsonio

__all__: list[str] = [
    "TERMINAL_WORK_ITEM_STATUSES",
    "is_top_level_anchor_epic",
    "live_thread_slugs_for_repo",
    "reclaimable_live_thread_slugs",
]

TERMINAL_WORK_ITEM_STATUSES = frozenset({"closed", "done"})


def is_top_level_anchor_epic(
    *,
    item: Mapping[str, object],
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> bool:
    return is_plan_anchor_epic(item=item) or is_seat_anchor_epic(
        item=item,
        seat_anchor_epic_ids=seat_anchor_epic_ids,
    )


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


def reclaimable_live_thread_slugs(
    *,
    live_slugs: Sequence[str],
    work_items: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    occupied_slugs = open_work_item_plan_slugs(work_items=work_items)
    return tuple(slug for slug in live_slugs if slug not in occupied_slugs)


def is_plan_anchor_epic(*, item: Mapping[str, object]) -> bool:
    return is_epic(item=item) and plan_slug(item=item) is not None


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


def open_work_item_plan_slugs(*, work_items: Sequence[Mapping[str, object]]) -> frozenset[str]:
    anchor_slugs_by_id = plan_anchor_slugs_by_id(work_items=work_items)
    occupied: set[str] = set()
    for item in work_items:
        status = item.get("status")
        if isinstance(status, str) and status.lower() in TERMINAL_WORK_ITEM_STATUSES:
            continue
        if is_plan_anchor_epic(item=item):
            continue
        slug = item_plan_slug(item=item, anchor_slugs_by_id=anchor_slugs_by_id)
        if slug is not None:
            occupied.add(slug)
    return frozenset(occupied)


def plan_anchor_slugs_by_id(
    *,
    work_items: Sequence[Mapping[str, object]],
) -> Mapping[str, str]:
    slugs_by_id: dict[str, str] = {}
    for item in work_items:
        if not is_plan_anchor_epic(item=item):
            continue
        identifier = work_item_id(item=item)
        slug = cast("str", plan_slug(item=item))
        slugs_by_id[identifier or ""] = slug
    return slugs_by_id


def item_plan_slug(
    *,
    item: Mapping[str, object],
    anchor_slugs_by_id: Mapping[str, str],
) -> str | None:
    parent = non_blank_text(value=item.get("parent"))
    return plan_slug(item=item) or anchor_slugs_by_id.get(parent or "")


def work_item_id(*, item: Mapping[str, object]) -> str | None:
    value = item.get("id")
    return value if isinstance(value, str) and value != "" else None


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
