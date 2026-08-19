"""Typed read path for mapping rows: valid Tracks plus surfaced invalid rows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TypeAlias

from _registry_core import Track, file_lock, resolve_store, warn
from _registry_resume import normalize_rows
from _registry_row_fields import ctx_threshold_from_row, model_profile_from_row, opt_str_from_row
from _registry_rows_io import RawMappingRow, read_row_records, read_rows, write_rows

__all__: list[str] = [
    "MappingEntry",
    "MappingInvalid",
    "MappingValid",
    "read_mapping",
    "read_valid_mapping",
]


@dataclass(frozen=True, kw_only=True)
class MappingValid:
    track: Track


@dataclass(frozen=True, kw_only=True)
class MappingInvalid:
    reason: str
    raw_line: str
    lineno: int


MappingEntry: TypeAlias = MappingValid | MappingInvalid


def _track_from_record(*, record: RawMappingRow) -> MappingEntry:
    row = record.row
    topic = row.get("topic")
    repo = row.get("repo")
    if not isinstance(topic, str) or not isinstance(repo, str):
        return MappingInvalid(
            reason="missing_topic_or_repo",
            raw_line=record.raw_line,
            lineno=record.lineno,
        )
    return MappingValid(
        track=Track(
            topic=topic,
            repo=repo,
            tmux=opt_str_from_row(row=row, key="tmux"),
            resume=opt_str_from_row(row=row, key="resume"),
            epic=opt_str_from_row(row=row, key="epic"),
            ctx_threshold=ctx_threshold_from_row(row=row),
            pinned_session_id=opt_str_from_row(row=row, key="pinned_session_id"),
            observed_session_identity=opt_str_from_row(row=row, key="observed_session_identity"),
            added_at=opt_str_from_row(row=row, key="added_at"),
            model_profile=model_profile_from_row(row=row, repo=repo, topic=topic),
            assigned=True,
        )
    )


def read_mapping(*, store_path: str | os.PathLike[str] | None = None) -> list[MappingEntry]:
    """Read mapping object rows into Valid/Invalid entries without failing wholesale."""
    path = resolve_store(store_path=store_path)
    rows = read_rows(store_path=store_path)
    if normalize_rows(rows=rows):
        with file_lock(target=path):
            rows = read_rows(store_path=store_path)
            _ = normalize_rows(rows=rows)
            write_rows(rows=rows, store_path=store_path)
    return [_track_from_record(record=record) for record in read_row_records(store_path=store_path)]


def read_valid_mapping(*, store_path: str | os.PathLike[str] | None = None) -> list[Track]:
    """Read Tracks for existing callers, reporting invalid object rows fail-soft."""
    tracks: list[Track] = []
    for entry in read_mapping(store_path=store_path):
        if isinstance(entry, MappingValid):
            tracks.append(entry.track)
        else:
            warn(
                message=(f"invalid mapping row {entry.lineno}: {entry.reason}: {entry.raw_line!r}")
            )
    return tracks
