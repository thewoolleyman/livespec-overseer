"""Ledger value normalization for grooming conformance checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import cast

import jsonio
from foreman_gather_sources import parse_repo_config
from grooming_plan_budget import TERMINAL_WORK_ITEM_STATUSES, is_top_level_anchor_epic

__all__: list[str] = [
    "TERMINAL_STATUSES",
    "cross_repo_payload_breaches",
    "has_dependency_payload",
    "has_parent",
    "is_open",
    "item_contains_delimiter",
    "item_id",
    "labels",
    "listed_sibling_repos",
    "merged_acceptance_criteria",
    "needs_plan_rollup",
    "sorted_ids",
    "status",
]

TERMINAL_STATUSES = TERMINAL_WORK_ITEM_STATUSES
OPENING_TEMPLATE_DELIMITERS = (
    chr(123) * 2,
    chr(123) + "%",
    chr(123) + "#",
)


def merged_acceptance_criteria(*, item: Mapping[str, object]) -> str | None:
    native = non_blank_text(value=item.get("acceptance_criteria"))
    if native is not None:
        return native
    metadata = jsonio.as_object(value=item.get("metadata")) or {}
    return non_blank_text(value=metadata.get("acceptance_criteria"))


def item_contains_delimiter(
    *,
    item: Mapping[str, object],
    detail_texts: Sequence[str],
) -> bool:
    return any(
        delimiter in text
        for text in item_texts(item=item, details=detail_texts)
        for delimiter in OPENING_TEMPLATE_DELIMITERS
    )


def item_texts(*, item: Mapping[str, object], details: Sequence[str]) -> tuple[str, ...]:
    texts = [
        text_or_empty(value=item.get("title")),
        text_or_empty(value=item.get("description")),
        merged_acceptance_criteria(item=item) or "",
    ]
    metadata = jsonio.as_object(value=item.get("metadata")) or {}
    texts.append(text_or_empty(value=metadata.get("notes")))
    texts.extend(details)
    return tuple(texts)


def cross_repo_payload_breaches(
    *,
    item: Mapping[str, object],
    listed_repos: frozenset[str],
    sibling_item_ids_by_repo: Mapping[str, frozenset[str]],
) -> bool:
    entries = mapping_sequence(value=dependency_payload(item=item))
    if entries is None:
        return True
    for entry in entries:
        repo = entry.get("repo")
        work_item_id = entry.get("work_item_id")
        if not isinstance(repo, str) or repo not in listed_repos:
            return True
        if not isinstance(work_item_id, str) or work_item_id not in sibling_item_ids_by_repo.get(
            repo, frozenset()
        ):
            return True
    return False


def listed_sibling_repos(*, repo: Path) -> frozenset[str]:
    config = parse_repo_config(repo=repo) or {}
    targets = jsonio.as_object(value=config.get("cross_repo_targets")) or {}
    return frozenset(targets)


def has_dependency_payload(*, item: Mapping[str, object]) -> bool:
    return dependency_payload(item=item) is not None


def needs_plan_rollup(
    *,
    item: Mapping[str, object],
    seat_anchor_epic_ids: AbstractSet[str] | None = None,
) -> bool:
    return is_open(item=item) and not is_top_level_anchor_epic(
        item=item,
        seat_anchor_epic_ids=seat_anchor_epic_ids,
    )


def is_open(*, item: Mapping[str, object]) -> bool:
    return status(item=item) not in TERMINAL_STATUSES


def has_parent(*, item: Mapping[str, object]) -> bool:
    value = item.get("parent")
    return isinstance(value, str) and value.strip() != ""


def labels(*, item: Mapping[str, object]) -> frozenset[str]:
    return frozenset(string_sequence(value=item.get("labels")))


def status(*, item: Mapping[str, object]) -> str:
    value = item.get("status")
    return value.lower() if isinstance(value, str) else ""


def item_id(*, item: Mapping[str, object]) -> str:
    value = item.get("id")
    return value if isinstance(value, str) else ""


def sorted_ids(*, items: Iterable[Mapping[str, object]]) -> tuple[str, ...]:
    return tuple(sorted(item_id(item=item) for item in items if item_id(item=item) != ""))


def dependency_payload(*, item: Mapping[str, object]) -> object:
    metadata = jsonio.as_object(value=item.get("metadata")) or {}
    payload = metadata.get("non_local_depends_on")
    if payload is not None:
        return payload
    return item.get("depends_on")


def mapping_sequence(*, value: object) -> tuple[Mapping[str, object], ...] | None:
    if not isinstance(value, list):
        return None
    entries: list[Mapping[str, object]] = []
    for entry in cast(list[object], value):
        parsed = jsonio.as_object(value=entry)
        if parsed is None:
            return None
        entries.append(parsed)
    return tuple(entries)


def string_sequence(*, value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    strings: list[str] = []
    for entry in cast(list[object], value):
        if isinstance(entry, str):
            strings.append(entry)
    return tuple(strings)


def non_blank_text(*, value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped != "" else None


def text_or_empty(*, value: object) -> str:
    return value if isinstance(value, str) else ""
