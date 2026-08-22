"""Invariant checks kept outside the core invariant module.

One invariant is structurally guaranteed by the tenant rather than measured
from a row field. Another is measured against SIBLING repositories rather than
against the items under scan, so it carries inputs the rest of the suite does
not. The split-acceptance label check stays here because its label half is now
measured while its criteria-shape half remains deliberately unexpressed.

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
    is_open,
    is_resolved_local_dependency,
    item_id,
    labels,
    listed_sibling_repos,
    mapping_sequence,
    sorted_ids,
)

__all__: list[str] = [
    "cross_repo_dependency_check",
    "routing_field_pending",
    "split_acceptance_label_pending",
]


ACCEPTANCE_LABEL_PREFIX = "acceptance:"
ACCEPTANCE_POLICIES = frozenset({"ai-only", "ai-then-human", "human-only"})


def split_acceptance_label_pending(
    *,
    items: Sequence[Mapping[str, object]],
) -> InvariantCheck:
    scanned = tuple(item for item in items if is_open(item=item))
    breaches = sorted_ids(
        items=(
            item
            for item in scanned
            if acceptance_labels(item=item) != expected_acceptance_labels(item=item)
        )
    )
    return InvariantCheck(
        key="split-acceptance-label",
        title="Acceptance-policy label and merged acceptance policy agree",
        status="checked",
        breaching_item_ids=breaches,
        scanned_item_count=len(scanned),
        scope=split_acceptance_label_scope(items=scanned),
        reason=(
            "checks only the label-versus-acceptance_policy half; split-criteria "
            "shape remains unexpressed in the substrate"
        ),
    )


def acceptance_labels(*, item: Mapping[str, object]) -> frozenset[str]:
    return frozenset(
        label for label in labels(item=item) if label.startswith(ACCEPTANCE_LABEL_PREFIX)
    )


def expected_acceptance_labels(*, item: Mapping[str, object]) -> frozenset[str]:
    policy = acceptance_policy(item=item)
    if policy is None:
        return frozenset()
    return frozenset({f"{ACCEPTANCE_LABEL_PREFIX}{policy}"})


def acceptance_policy(*, item: Mapping[str, object]) -> str | None:
    value = item.get("acceptance_policy")
    if isinstance(value, str) and value in ACCEPTANCE_POLICIES:
        return value
    return None


def split_acceptance_label_scope(*, items: Sequence[Mapping[str, object]]) -> str:
    policy_count = sum(1 for item in items if acceptance_policy(item=item) is not None)
    policyless_count = len(items) - policy_count
    return (
        f"{len(items)} open rows from the merged projection; {policy_count} "
        f"policy-bearing rows and {policyless_count} policy-less rows compared "
        "acceptance-prefixed labels to acceptance_policy; split-criteria shape "
        "remains unexpressed in the substrate"
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
        title="Tenant structurally pins the deliverable repository",
        status="structurally-guaranteed",
        breaching_item_ids=(),
        scanned_item_count=0,
        scope="no row-level routing field is scanned",
        reason=(
            "no backing routing field exists on the work item or merged projection; "
            "the tenant is per-repo, so the deliverable repository is pinned "
            "structurally"
        ),
    )
