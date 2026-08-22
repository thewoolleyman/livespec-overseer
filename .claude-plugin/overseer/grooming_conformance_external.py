"""Invariant checks that this tenant's own item list cannot decide.

Two are declared and deliberately unimplemented: their verdicts are fixed
reports naming what a decision would have to legislate first.  The third is
measured, but against SIBLING repositories rather than against the items under
scan, so it carries inputs the rest of the suite does not.

They live apart from `grooming_conformance_invariants` for that reason rather
than for size: everything left there is decided by the scanned items alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path

from grooming_conformance_types import InvariantCheck
from grooming_conformance_values import (
    cross_repo_payload_breaches,
    has_dependency_payload,
    listed_sibling_repos,
    sorted_ids,
)

__all__: list[str] = [
    "cross_repo_dependency_check",
    "routing_field_pending",
    "split_acceptance_label_pending",
]


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
