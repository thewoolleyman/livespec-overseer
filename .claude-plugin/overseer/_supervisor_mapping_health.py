"""Read-only mapping-row health projection for operator-visible rows."""

from __future__ import annotations

import os
from dataclasses import replace

import registry
from _registry_rows_io import read_rows
from _supervisor_view import RowView

__all__: list[str] = ["apply_mapping_health", "explicit_null_added_at_keys"]

MappingKey = tuple[str, str]


def explicit_null_added_at_keys(
    *, store_path: str | os.PathLike[str] | None
) -> frozenset[MappingKey]:
    keys: set[MappingKey] = set()
    for row in read_rows(store_path=store_path):
        repo = row.get("repo")
        topic = row.get("topic")
        if (
            isinstance(repo, str)
            and isinstance(topic, str)
            and "added_at" in row
            and row.get("added_at") is None
        ):
            keys.add((registry.norm(repo=repo), topic))
    return frozenset(keys)


def _unusable_reason(
    *, track: registry.Track, null_added_at_keys: frozenset[MappingKey]
) -> str | None:
    if not isinstance(track, registry.PlanTrack):
        return None
    key = (registry.norm(repo=track.repo), track.topic)
    if key in null_added_at_keys:
        return "mapping row missing added_at; no-round ready cannot certify"
    if not registry.epic_is_resolved(epic=track.epic):
        return "mapping row has unresolved epic; restart resume cannot be built"
    return None


def apply_mapping_health(
    *, track: registry.Track, row: RowView, null_added_at_keys: frozenset[MappingKey]
) -> RowView:
    reason = _unusable_reason(track=track, null_added_at_keys=null_added_at_keys)
    if reason is None:
        return row
    return replace(row, status="mapping-unusable", note=reason)
