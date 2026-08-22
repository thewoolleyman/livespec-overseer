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
    dependency_payload,
    has_dependency_payload,
    is_resolved_local_dependency,
    item_id,
    listed_sibling_repos,
    mapping_sequence,
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
    sibling_item_ids_by_repo: Mapping[str, AbstractSet[str]] | None,
) -> InvariantCheck:
    """Evaluate cross-repo edges only when their sibling id registers exist.

    Missing sibling id sets make resolution unevaluated, not breached: an empty
    evidence base cannot distinguish a healthy edge from a broken one.
    """

    siblings = {
        repo_slug: frozenset(item_ids)
        for repo_slug, item_ids in (sibling_item_ids_by_repo or {}).items()
    }
    local_item_ids = frozenset(item_id(item=item) for item in items if item_id(item=item) != "")
    listed_repos = listed_sibling_repos(repo=repo)
    candidates = tuple(item for item in items if has_dependency_payload(item=item))
    missing_repos = missing_sibling_evidence_repos(
        items=candidates,
        local_item_ids=local_item_ids,
        listed_repos=listed_repos,
        sibling_item_ids_by_repo=siblings,
    )
    if missing_repos:
        return InvariantCheck(
            key="cross-repo-dependencies",
            title="Cross-repo dependency edges resolve in listed sibling repos",
            status="unevaluated-missing-evidence",
            breaching_item_ids=(),
            scanned_item_count=len(candidates),
            scope=missing_sibling_evidence_scope(missing_repos=missing_repos),
            reason=(
                "cross-repo resolution requires sibling item id sets; missing sets "
                "would turn every referenced id for that repo into a false breach"
            ),
        )
    breaches = sorted_ids(
        items=(
            item
            for item in candidates
            if cross_repo_payload_breaches(
                item=item,
                local_item_ids=local_item_ids,
                listed_repos=listed_repos,
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


def missing_sibling_evidence_repos(
    *,
    items: Sequence[Mapping[str, object]],
    local_item_ids: frozenset[str],
    listed_repos: frozenset[str],
    sibling_item_ids_by_repo: Mapping[str, frozenset[str]],
) -> tuple[str, ...]:
    missing: set[str] = set()
    for item in items:
        entries = mapping_sequence(value=dependency_payload(item=item))
        if entries is None:
            continue
        for entry in entries:
            if is_resolved_local_dependency(entry=entry, local_item_ids=local_item_ids):
                continue
            repo = entry.get("repo")
            if (
                isinstance(repo, str)
                and repo in listed_repos
                and repo not in sibling_item_ids_by_repo
            ):
                missing.add(repo)
    return tuple(sorted(missing))


def missing_sibling_evidence_scope(*, missing_repos: tuple[str, ...]) -> str:
    missing = ", ".join(missing_repos)
    noun = "repo" if len(missing_repos) == 1 else "repos"
    return (
        f"bulk rows carrying dependency payloads; no sibling id set supplied for "
        f"{noun} {missing}, so no resolution was attempted against it"
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
