"""Field-scoped updates for existing registry mapping rows."""

from __future__ import annotations

import os

from _registry_core import (
    file_lock,
    norm,
    resolve_store,
    warn,
)
from _registry_rows_io import read_rows, write_rows
from _registry_store_rows import validated_row

__all__: list[str] = [
    "record_derived_epic",
    "record_model_profile",
    "record_observed_session_identity",
    "repoint_tmux",
    "set_epic",
]


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
                    validated = validated_row(row=candidate)
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
