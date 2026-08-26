"""The durable mapping store — read / append / remove-by-(repo,topic) / rewrite-filter.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. JSONL = one JSON object per line; a malformed line fails
SOFT. `registry.py` re-exports this surface, so consumers keep importing `registry`.
"""

from __future__ import annotations

import json
import os

from _registry_core import (
    Track,
    file_lock,
    norm,
    resolve_store,
    warn,
)
from _registry_rows_io import read_rows, write_rows
from _registry_store_fields import (
    record_derived_epic,
    record_model_profile,
    record_observed_session_identity,
    repoint_tmux,
    set_epic,
)
from _registry_store_rows import track_to_row, validated_row
from _registry_store_upsert_write import write_upsert_rows
from _registry_upsert_fields import apply_upsert_update_fields
from _seams import MappingRowPredicate

_DEFAULT_UPSERT_UPDATE_FIELDS = frozenset({"tmux"})

__all__: list[str] = [
    "append_mapping",
    "record_derived_epic",
    "record_model_profile",
    "record_observed_session_identity",
    "remove_mapping",
    "repoint_tmux",
    "rewrite_mapping",
    "set_epic",
    "track_to_row",
    "upsert_mapping",
    "validated_row",
]


def append_mapping(
    *,
    track: Track,
    store_path: str | os.PathLike[str] | None = None,
    added_at: str | None = None,
) -> None:
    """Append one mapping row (durable keys + optional ``added_at`` stamp).

    Under a store lock so a concurrent :func:`rewrite_mapping` cannot read a
    snapshot that predates this append and write it back, silently dropping the
    freshly-added live row (B6). Fail-soft on an OSError (B7).
    """
    path = resolve_store(store_path=store_path)
    row = track_to_row(track=track)
    if row.get("added_at") is None:
        _ = row.pop("added_at", None)
    if added_at is not None:
        row["added_at"] = added_at
    with file_lock(target=path):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                _ = handle.write(json.dumps(row) + "\n")
        except OSError as exc:
            warn(message=f"could not append to {path}: {exc}")


def upsert_mapping(
    *,
    track: Track,
    store_path: str | os.PathLike[str] | None = None,
    added_at: str | None = None,
    update_fields: frozenset[str] = _DEFAULT_UPSERT_UPDATE_FIELDS,
) -> bool:
    """Ensure one ``(repo, topic)`` row exists while preserving durable row fields."""
    path = resolve_store(store_path=store_path)
    repo_norm = norm(repo=track.repo)
    new_row = track_to_row(track=track)
    if added_at is not None:
        new_row["added_at"] = added_at
    with file_lock(target=path):
        rows = read_rows(store_path=store_path)
        matching_indexes = [
            index
            for index, row in enumerate(rows)
            if (
                isinstance(row_repo := row.get("repo"), str)
                and norm(repo=row_repo) == repo_norm
                and row.get("topic") == track.topic
            )
        ]
        if not matching_indexes:
            rows.append(new_row)
            return write_upsert_rows(rows=rows, store_path=store_path, path=path)
        changed = len(matching_indexes) > 1
        row = rows[matching_indexes[0]]
        changed = (
            apply_upsert_update_fields(
                row=row, new_row=new_row, track=track, update_fields=update_fields
            )
            or changed
        )
        if len(matching_indexes) > 1:
            duplicate_indexes = set(matching_indexes[1:])
            rows = [row for index, row in enumerate(rows) if index not in duplicate_indexes]
        if changed:
            return write_upsert_rows(rows=rows, store_path=store_path, path=path)
        return True


def rewrite_mapping(
    *,
    keep: MappingRowPredicate,
    store_path: str | os.PathLike[str] | None = None,
) -> int:
    """Rewrite the store keeping only rows where ``keep(row)`` is true.

    Returns the number of rows dropped. Operates on raw dicts so unknown keys
    survive. The daemon's archive-GC uses this with a predicate built from
    :func:`archived_or_gone`. Held under a store lock so the read-modify-write is
    atomic against a concurrent append (B6); SKIPS the write entirely when no row
    is dropped, so a steady-state tick does not rewrite (and risk truncating) the
    store on every pass.
    """
    with file_lock(target=resolve_store(store_path=store_path)):
        rows = read_rows(store_path=store_path)
        kept = [row for row in rows if keep(row=row)]
        if len(kept) != len(rows):
            # Every kept row is carried VERBATIM and every dropped row is a whole
            # row, so the write-predicate has nothing here it can refuse: removing
            # a row entirely is not removing its epic. The result is ignored for
            # that reason, not overlooked.
            _ = write_rows(rows=kept, store_path=store_path)
        return len(rows) - len(kept)


def remove_mapping(
    *,
    repo: str,
    topic: str,
    store_path: str | os.PathLike[str] | None = None,
) -> int:
    """Remove the mapping row(s) matching ``(repo, topic)``; return the count."""
    repo_norm = norm(repo=repo)

    def _keep(*, row: dict[str, object]) -> bool:
        row_repo = row.get("repo")
        return not (
            isinstance(row_repo, str)
            and norm(repo=row_repo) == repo_norm
            and row.get("topic") == topic
        )

    return rewrite_mapping(keep=_keep, store_path=store_path)
