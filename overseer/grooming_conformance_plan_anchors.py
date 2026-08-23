"""Plan-anchor metadata conformance for the grooming drain pass."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import jsonio
from grooming_conformance_types import InvariantCheck
from grooming_plan_budget import TERMINAL_WORK_ITEM_STATUSES

__all__: list[str] = ["plan_anchor_metadata_check"]


def plan_anchor_metadata_check(
    *,
    repo: Path,
    items: Sequence[Mapping[str, object]],
) -> InvariantCheck:
    plan_dirs = live_plan_directory_slugs(repo=repo)
    anchors_by_slug = plan_anchor_epic_ids_by_slug(items=items)
    breaching = [
        breach
        for slug in plan_dirs
        for breach in anchor_breaches(slug=slug, anchor_ids=anchors_by_slug.get(slug, ()))
    ]
    return InvariantCheck(
        key="plan-anchor-metadata",
        title="Every live plan directory has exactly one ledger metadata anchor",
        status="checked",
        breaching_item_ids=tuple(sorted(breaching)),
        scanned_item_count=len(plan_dirs),
        scope="live plan directories and non-terminal same-tenant epic rows",
        reason=(
            "each live plan directory must have exactly one same-tenant epic with "
            "metadata plan_slug equal to the directory name; this local check does "
            "not delegate to plan_epic_parity until livespec-dev-tooling-aqmr fixes "
            "that reader's false-fail behavior"
        ),
    )


def live_plan_directory_slugs(*, repo: Path) -> tuple[str, ...]:
    plan_dir = repo / "plan"
    entries = tuple(plan_dir.iterdir())
    return tuple(
        sorted(entry.name for entry in entries if entry.is_dir() and entry.name != "archive")
    )


def plan_anchor_epic_ids_by_slug(
    *,
    items: Sequence[Mapping[str, object]],
) -> Mapping[str, tuple[str, ...]]:
    ids_by_slug: dict[str, list[str]] = {}
    for item in items:
        if not is_open_epic(item=item):
            continue
        slug = metadata_plan_slug(item=item)
        identifier = item_id(item=item)
        if slug is not None and identifier is not None:
            ids_by_slug.setdefault(slug, []).append(identifier)
    return {slug: tuple(sorted(ids)) for slug, ids in ids_by_slug.items()}


def anchor_breaches(*, slug: str, anchor_ids: Sequence[str]) -> tuple[str, ...]:
    if len(anchor_ids) == 1:
        return ()
    if len(anchor_ids) == 0:
        return (f"plan/{slug}",)
    return tuple(anchor_ids)


def is_open_epic(*, item: Mapping[str, object]) -> bool:
    issue_type = item.get("issue_type") or item.get("type")
    return issue_type == "epic" and item_status(item=item) not in TERMINAL_WORK_ITEM_STATUSES


def metadata_plan_slug(*, item: Mapping[str, object]) -> str | None:
    metadata = jsonio.as_object(value=item.get("metadata"))
    if metadata is None:
        return None
    value = metadata.get("plan_slug")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped != "" else None


def item_id(*, item: Mapping[str, object]) -> str | None:
    value = item.get("id")
    return value if isinstance(value, str) and value != "" else None


def item_status(*, item: Mapping[str, object]) -> str:
    value = item.get("status")
    return value.lower() if isinstance(value, str) else ""
