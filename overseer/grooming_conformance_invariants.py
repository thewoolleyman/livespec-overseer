"""Invariant evaluation for the grooming drain pass."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi.25

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path

from grooming_conformance_types import GroomingConformanceReport, InvariantCheck
from grooming_conformance_values import (
    cross_repo_payload_breaches,
    has_dependency_payload,
    has_parent,
    is_open,
    item_contains_delimiter,
    item_id,
    listed_sibling_repos,
    merged_acceptance_criteria,
    needs_plan_rollup,
    sorted_ids,
    status,
)
from grooming_plan_budget import is_top_level_anchor_epic

__all__: list[str] = [
    "evaluate_ledger_invariants",
    "merged_acceptance_criteria",
]

LIFECYCLE_STATUSES = frozenset(
    {
        "acceptance",
        "active",
        "backlog",
        "blocked",
        "closed",
        "pending-approval",
        "ready",
    }
)
DISPATCHABLE_STATUSES = frozenset({"pending-approval", "ready"})


def evaluate_ledger_invariants(
    *,
    repo: str | Path,
    work_items: Sequence[Mapping[str, object]],
    item_details_by_id: Mapping[str, Sequence[str]] | None = None,
    sibling_item_ids_by_repo: Mapping[str, AbstractSet[str]] | None = None,
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> GroomingConformanceReport:
    repo_path = Path(repo)
    items = tuple(work_items)
    details = item_details_by_id or {}
    siblings = sibling_item_ids_by_repo or {}
    item_ids = tuple(sorted(item_id(item=item) for item in items if item_id(item=item) != ""))
    return GroomingConformanceReport(
        repo=str(repo_path),
        scanned_item_count=len(items),
        scanned_item_ids=item_ids,
        invariants=(
            plan_rollup_check(items=items, seat_anchor_epic_ids=seat_anchor_epic_ids),
            acceptance_present_check(items=items, seat_anchor_epic_ids=seat_anchor_epic_ids),
            lifecycle_status_check(items=items),
            dispatchable_delimiter_check(items=items, item_details_by_id=details),
            split_acceptance_label_pending(),
            cross_repo_dependency_check(
                repo=repo_path,
                items=items,
                sibling_item_ids_by_repo=siblings,
            ),
            routing_field_pending(),
        ),
    )


def plan_rollup_check(
    *,
    items: Sequence[Mapping[str, object]],
    seat_anchor_epic_ids: AbstractSet[str] | None,
) -> InvariantCheck:
    scanned = tuple(
        item
        for item in items
        if needs_plan_rollup(item=item, seat_anchor_epic_ids=seat_anchor_epic_ids)
    )
    return InvariantCheck(
        key="plan-rollup",
        title="Every non-done item rolls up to a plan epic",
        status="checked",
        breaching_item_ids=sorted_ids(items=(i for i in scanned if not has_parent(item=i))),
        scanned_item_count=len(scanned),
        scope=anchor_scope(suffix="bulk ledger rows", seat_anchor_epic_ids=seat_anchor_epic_ids),
    )


def acceptance_present_check(
    *,
    items: Sequence[Mapping[str, object]],
    seat_anchor_epic_ids: AbstractSet[str] | None,
) -> InvariantCheck:
    scanned = tuple(
        item
        for item in items
        if is_open(item=item)
        and not is_top_level_anchor_epic(item=item, seat_anchor_epic_ids=seat_anchor_epic_ids)
    )
    return InvariantCheck(
        key="acceptance-present",
        title="Every open item carries acceptance criteria",
        status="checked",
        breaching_item_ids=sorted_ids(
            items=(i for i in scanned if merged_acceptance_criteria(item=i) is None)
        ),
        scanned_item_count=len(scanned),
        scope=anchor_scope(
            suffix="rows using the merged acceptance projection",
            seat_anchor_epic_ids=seat_anchor_epic_ids,
        ),
    )


def anchor_scope(*, suffix: str, seat_anchor_epic_ids: AbstractSet[str] | None) -> str:
    if seat_anchor_epic_ids is not None:
        return f"non-terminal, non-plan-anchor, non-seat-anchor {suffix}"
    return (
        f"non-terminal, non-plan-anchor {suffix}; seat-anchor register not supplied, "
        "so no non-seat-anchor exclusion was applied"
    )


def lifecycle_status_check(*, items: Sequence[Mapping[str, object]]) -> InvariantCheck:
    breaches = sorted_ids(
        items=(item for item in items if status(item=item) not in LIFECYCLE_STATUSES)
    )
    return InvariantCheck(
        key="lifecycle-status",
        title="Only lifecycle statuses exist",
        status="checked",
        breaching_item_ids=breaches,
        scanned_item_count=len(items),
        scope="all rows from the bulk ledger projection",
    )


def dispatchable_delimiter_check(
    *,
    items: Sequence[Mapping[str, object]],
    item_details_by_id: Mapping[str, Sequence[str]],
) -> InvariantCheck:
    scanned = tuple(item for item in items if status(item=item) in DISPATCHABLE_STATUSES)
    breaches = sorted_ids(
        items=(
            item
            for item in scanned
            if item_contains_delimiter(
                item=item,
                detail_texts=item_details_by_id.get(item_id(item=item), ()),
            )
        )
    )
    return InvariantCheck(
        key="dispatchable-delimiter",
        title="No dispatchable item carries a brace template delimiter",
        status="checked",
        breaching_item_ids=breaches,
        scanned_item_count=len(scanned),
        scope="dispatchable rows, including supplied detail text for comments and notes",
    )


def split_acceptance_label_pending() -> InvariantCheck:
    return InvariantCheck(
        key="split-acceptance-label",
        title="Human-verified-acceptance label and split acceptance agree",
        status="unimplemented-pending-decision",
        breaching_item_ids=(),
        scanned_item_count=0,
        scope="not mechanically checked",
        reason=(
            "the label is defined, but there is no canonical expression of split "
            "acceptance; choosing one here would legislate schema"
        ),
    )


def cross_repo_dependency_check(
    *,
    repo: Path,
    items: Sequence[Mapping[str, object]],
    sibling_item_ids_by_repo: Mapping[str, AbstractSet[str]],
) -> InvariantCheck:
    siblings = {
        repo_slug: frozenset(item_ids) for repo_slug, item_ids in sibling_item_ids_by_repo.items()
    }
    candidates = tuple(item for item in items if has_dependency_payload(item=item))
    breaches = sorted_ids(
        items=(
            item
            for item in candidates
            if cross_repo_payload_breaches(
                item=item,
                listed_repos=listed_sibling_repos(repo=repo),
                sibling_item_ids_by_repo=siblings,
            )
        )
    )
    return InvariantCheck(
        key="cross-repo-dependencies",
        title="Cross-repo dependency edges resolve in listed sibling repos",
        status="checked",
        breaching_item_ids=breaches,
        scanned_item_count=len(candidates),
        scope="bulk rows carrying dependency payloads, with sibling id sets supplied in bulk",
    )


def routing_field_pending() -> InvariantCheck:
    return InvariantCheck(
        key="routing-field",
        title="Routing field names the deliverable repository",
        status="unimplemented-pending-decision",
        breaching_item_ids=(),
        scanned_item_count=0,
        scope="not mechanically checked",
        reason=(
            "no backing field exists on the work item or metadata; the tenant itself "
            "pins the repository"
        ),
    )
