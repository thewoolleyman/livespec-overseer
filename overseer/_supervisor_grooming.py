"""Grooming reserved-entity row source for the daemon tick."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import _supervisor_evaluate
import _supervisor_mapping_health
import grooming_runtime
import registry
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "grooming_evaluation_row",
    "grooming_rows",
    "grooming_track",
]


def grooming_track(
    *, repo: str, store_path: str | os.PathLike[str] | None = None
) -> registry.Track | None:
    topic = grooming_runtime.canonical_session_name(repo=repo)
    repo_norm = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=store_path):
        if registry.norm(repo=track.repo) == repo_norm and track.topic == topic:
            return track
    return None


def grooming_evaluation_row(
    *,
    sup: Supervisor,
    repo: str,
    act: bool,
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey] = frozenset(),
) -> RowView | None:
    track = grooming_track(repo=repo, store_path=sup.store_path)
    if track is None:
        return None
    row = _supervisor_evaluate.evaluate(sup=sup, track=track, act=act)
    if act:
        return row
    return _supervisor_mapping_health.apply_mapping_health(
        track=track, row=row, null_added_at_keys=null_added_at_keys
    )


def grooming_rows(
    *,
    sup: Supervisor,
    repos: list[str],
    act: bool,
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey] = frozenset(),
) -> list[RowView]:
    rows: list[RowView] = []
    for repo in repos:
        evaluation_row = grooming_evaluation_row(
            sup=sup,
            repo=repo,
            act=act,
            null_added_at_keys=null_added_at_keys,
        )
        if evaluation_row is not None:
            rows.append(evaluation_row)
    return rows
