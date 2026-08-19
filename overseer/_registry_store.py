"""The durable mapping store — read / append / remove-by-(repo,topic) / rewrite-filter.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. JSONL = one JSON object per line; a malformed line fails
SOFT. `registry.py` re-exports this surface, so consumers keep importing `registry`.
"""
# livespec-lloc-soft-band-owner: overseer-hgq4wi.5

from __future__ import annotations

import json
import os

from _registry_core import (
    SupervisorSeat,
    Track,
    file_lock,
    norm,
    resolve_store,
    warn,
)
from _registry_resume import normalize_resume_override
from _registry_row_fields import ctx_threshold_from_row, model_profile_from_row, opt_str_from_row
from _registry_rows_io import read_rows, write_rows
from _registry_track_row_parse import RowExtras, track_from_mapping_row
from _seams import MappingRowPredicate

__all__: list[str] = [
    "append_mapping",
    "record_derived_epic",
    "record_model_profile",
    "record_observed_session_identity",
    "remove_mapping",
    "repoint_tmux",
    "rewrite_mapping",
    "set_epic",
    "upsert_mapping",
]


def _track_to_row(*, track: Track) -> dict[str, object]:
    # A legacy row's `handoff` key is READ without error (it is simply not mapped onto
    # any Track field) and is dropped here, so the first rewrite that touches such a row
    # retires the key. The store never emits it: a track's read-first source is the plan
    # state held on its ledger `epic`, and a second, path-shaped copy of that answer is
    # exactly the drift the locator replaced.
    row: dict[str, object] = {
        "kind": track.kind,
        "topic": track.topic,
        "repo": track.repo,
        "tmux": track.tmux,
        "resume": track.resume,
        "epic": track.epic,
        "pinned_session_id": track.pinned_session_id,
        "observed_session_identity": track.observed_session_identity,
        "added_at": track.added_at,
    }
    # OMIT ``ctx_threshold`` when there is no per-track override (None): a row
    # WITHOUT the key means "inherit the daemon default"; include it only for an
    # explicit int override.
    if track.ctx_threshold is not None:
        row["ctx_threshold"] = track.ctx_threshold
    if track.model_profile is not None:
        row["model_profile"] = track.model_profile
    if isinstance(track, SupervisorSeat):
        row["supervised_topic"] = track.supervised_topic
    _ = normalize_resume_override(row=row)
    return row


def _validated_row(*, row: dict[str, object]) -> dict[str, object]:
    topic = row.get("topic")
    repo = row.get("repo")
    track = track_from_mapping_row(
        row=row,
        extras=RowExtras(
            resume=opt_str_from_row(row=row, key="resume"),
            ctx_threshold=ctx_threshold_from_row(row=row),
            pinned_session_id=opt_str_from_row(row=row, key="pinned_session_id"),
            observed_session_identity=opt_str_from_row(row=row, key="observed_session_identity"),
            added_at=opt_str_from_row(row=row, key="added_at"),
            model_profile=model_profile_from_row(
                row=row,
                repo=repo if isinstance(repo, str) else "",
                topic=topic if isinstance(topic, str) else "",
            ),
        ),
    )
    serialized = _track_to_row(track=track)
    known = set(serialized)
    return {**{key: value for key, value in row.items() if key not in known}, **serialized}


def _update_matching_field(
    *,
    repo: str,
    topic: str,
    field: str,
    value: object,
    store_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Set ``field`` to ``value`` on the ``(repo, topic)`` row; return whether it changed.

    The shared shape behind :func:`record_observed_session_identity`,
    :func:`record_derived_epic`, and :func:`repoint_tmux`: find the matching row
    under the store lock, mutate one field in place (unknown keys survive —
    raw dicts, not Tracks), write only when something actually changed
    (idempotent, so a steady-state tick never rewrites the store), and
    no-op when there is no such row.
    """
    repo_norm = norm(repo=repo)
    with file_lock(target=resolve_store(store_path=store_path)):
        rows = read_rows(store_path=store_path)
        changed = False
        for row in rows:
            row_repo = row.get("repo")
            if (
                isinstance(row_repo, str)
                and norm(repo=row_repo) == repo_norm
                and row.get("topic") == topic
                and row.get(field) != value
            ):
                candidate = {**row, field: value}
                try:
                    validated = _validated_row(row=candidate)
                except ValueError as exc:
                    warn(
                        message=(
                            f"refusing invalid mapping update {repo_norm}::{topic} "
                            f"{field}: {exc}"
                        )
                    )
                    continue
                row.clear()
                row.update(validated)
                changed = True
        if changed:
            write_rows(rows=rows, store_path=store_path)
        return changed


def record_observed_session_identity(
    *,
    repo: str,
    topic: str,
    session_identity: str,
    store_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Persist that this mapped track has been observed with ``session_identity``."""
    return _update_matching_field(
        repo=repo,
        topic=topic,
        field="observed_session_identity",
        value=session_identity,
        store_path=store_path,
    )


def record_derived_epic(
    *,
    repo: str,
    topic: str,
    epic: str,
    store_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Persist a freshly-derived ``epic`` for the ``(repo, topic)`` mapping row.

    The restart interlock's one-shot re-derive (overseer-vbmq): a row whose
    ``epic`` was recorded ``None`` at assignment time stays ``None`` forever
    otherwise, since the daemon tick never calls `epic_from_plan_anchor` itself
    (assignment-only, by design).
    """
    return _update_matching_field(
        repo=repo, topic=topic, field="epic", value=epic, store_path=store_path
    )


set_epic = record_derived_epic


def record_model_profile(
    *,
    repo: str,
    topic: str,
    model_profile: dict[str, str | None],
    store_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Persist a freshly-read launch ``model_profile`` for the ``(repo, topic)`` row."""
    return _update_matching_field(
        repo=repo,
        topic=topic,
        field="model_profile",
        value=model_profile,
        store_path=store_path,
    )


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
    row = _track_to_row(track=track)
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
) -> None:
    """Ensure one ``(repo, topic)`` row exists while preserving durable row fields."""
    path = resolve_store(store_path=store_path)
    repo_norm = norm(repo=track.repo)
    new_row = _track_to_row(track=track)
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
            write_rows(rows=rows, store_path=store_path)
            return
        changed = len(matching_indexes) > 1
        row = rows[matching_indexes[0]]
        for field, value in (
            ("topic", track.topic),
            ("repo", track.repo),
            ("tmux", track.tmux),
        ):
            if row.get(field) != value:
                row[field] = value
                changed = True
        if len(matching_indexes) > 1:
            duplicate_indexes = set(matching_indexes[1:])
            rows = [row for index, row in enumerate(rows) if index not in duplicate_indexes]
        if changed:
            write_rows(rows=rows, store_path=store_path)


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
            write_rows(rows=kept, store_path=store_path)
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


def repoint_tmux(
    *,
    repo: str,
    topic: str,
    new_tmux: str,
    store_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Rewrite the ``(repo, topic)`` mapping row's ``tmux`` field to ``new_tmux``.

    The daemon uses this to RE-POINT a stale mapping: a topic's live named session that
    moved to a DIFFERENT tmux session than the store records (generic reused windows
    ``livespec1``… drift across topics), so the frozen binding would otherwise let an act
    target the wrong pane (R2, 2026-07-18). Operates on raw dicts under the store lock so
    unknown keys (``added_at``) survive and a concurrent append cannot clobber the update.

    Idempotent: returns False and SKIPS the write when no matching row needs changing (the
    stored ``tmux`` already equals ``new_tmux``, or there is no such row), so a steady-state
    tick where nothing moved never rewrites (and never risks truncating) the store. Returns
    True when at least one row was re-pointed. Fail-soft on OSError (inherited from
    :func:`write_rows`).
    """
    return _update_matching_field(
        repo=repo, topic=topic, field="tmux", value=new_tmux, store_path=store_path
    )
