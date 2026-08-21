"""Stage-level grooming conformance helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path

from grooming_conformance_invariants import (
    evaluate_ledger_invariants,
)
from grooming_conformance_types import (
    GroomingConformanceReport,
    GroomingMeasurement,
    GroomingStageReport,
    InvariantCheck,
)
from grooming_conformance_values import (
    has_parent,
    is_open,
    item_id,
    labels,
    merged_acceptance_criteria,
    needs_plan_rollup,
)
from grooming_plan_budget import resolve_plan_budget

__all__: list[str] = [
    "GroomingConformanceReport",
    "GroomingMeasurement",
    "GroomingStageReport",
    "InvariantCheck",
    "evaluate_ledger_invariants",
    "measure_grooming_inputs",
    "merged_acceptance_criteria",
    "verify_grooming_stage",
]

TRIAGED_LABEL = "intake:triaged"


def measure_grooming_inputs(
    *,
    repo: str | Path,
    work_items: Sequence[Mapping[str, object]],
    proposed_changes_count: int | None = None,
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> GroomingMeasurement:
    repo_path = Path(repo)
    items = tuple(work_items)
    open_ids = tuple(sorted(item_id(item=item) for item in items if is_open(item=item)))
    untriaged_ids = tuple(
        sorted(
            item_id(item=item)
            for item in items
            if is_open(item=item) and TRIAGED_LABEL not in labels(item=item)
        )
    )
    unparented_ids = tuple(
        sorted(
            item_id(item=item)
            for item in items
            if needs_plan_rollup(item=item, seat_anchor_epic_ids=seat_anchor_epic_ids)
            and not has_parent(item=item)
        )
    )
    budget = resolve_plan_budget(
        repo=repo_path,
        work_items=items,
        proposed_changes_count=proposed_changes_count,
        seat_anchor_epic_ids=seat_anchor_epic_ids,
    )
    return GroomingMeasurement(
        repo=str(repo_path),
        open_item_ids=open_ids,
        untriaged_item_ids=untriaged_ids,
        unparented_item_ids=unparented_ids,
        live_thread_slugs=budget.live_thread_slugs,
        open_item_digest=digest(values=open_ids),
        plan_budget=budget,
    )


def verify_grooming_stage(
    *,
    repo: str | Path,
    work_items: Sequence[Mapping[str, object]],
    proposed_changes_count: int | None = None,
    item_details_by_id: Mapping[str, Sequence[str]] | None = None,
    sibling_item_ids_by_repo: Mapping[str, AbstractSet[str]] | None = None,
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> GroomingStageReport:
    return GroomingStageReport(
        measurement=measure_grooming_inputs(
            repo=repo,
            work_items=work_items,
            proposed_changes_count=proposed_changes_count,
            seat_anchor_epic_ids=seat_anchor_epic_ids,
        ),
        conformance=evaluate_ledger_invariants(
            repo=repo,
            work_items=work_items,
            item_details_by_id=item_details_by_id,
            sibling_item_ids_by_repo=sibling_item_ids_by_repo,
            seat_anchor_epic_ids=seat_anchor_epic_ids,
        ),
    )


def digest(*, values: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()
