"""The durable mapping store — read / append / remove-by-(repo,topic) / rewrite-filter.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. JSONL = one JSON object per line; a malformed line fails
SOFT. `registry.py` re-exports this surface, so consumers keep importing `registry`.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable

import jsonio
from _registry_core import (
    Track,
    atomic_write,
    file_lock,
    norm,
    resolve_store,
    warn,
)
from _seams import MappingRowPredicate

__all__: list[str] = [
    "append_mapping",
    "read_mapping",
    "record_observed_session_identity",
    "remove_mapping",
    "repoint_tmux",
    "rewrite_mapping",
]

_PLAN_HANDOFF_RESUME = re.compile(
    r"(?<![\w.-])(?:[^\s`\"']*/)?plan/[^\s`\"']*/(?:supervisor-)?handoff\.md\b"
)


def _mentions_retired_plan_handoff(*, resume: str) -> bool:
    """Return True when a resume override names the retired plan-file shape."""
    return _PLAN_HANDOFF_RESUME.search(resume.replace("\\", "/")) is not None


def _plan_epic_resume(*, repo: str, epic: str) -> str:
    """Build the canonical plan-track resume prompt without importing prompt helpers."""
    return f"resume plan epic {epic} in repository {repo}; read its ledger-held plan state"


def _normalize_resume_override(*, row: dict[str, object]) -> bool:
    """Rewrite or clear retired plan-file resume overrides in-place.

    The detector is syntactic: a plan-tree ``handoff.md`` or
    ``supervisor-handoff.md`` resume is retired even if that path exists, and checking
    path existence here would violate the daemon's no-plan-file invariant.
    """
    resume = row.get("resume")
    if not isinstance(resume, str) or not _mentions_retired_plan_handoff(resume=resume):
        return False
    repo = row.get("repo")
    epic = row.get("epic")
    topic = row.get("topic")
    if isinstance(repo, str) and isinstance(epic, str):
        row["resume"] = _plan_epic_resume(repo=repo, epic=epic)
        warn(
            message=(
                "rewrote retired plan-file resume override to ledger epic resume "
                f"for {repo}::{topic}"
            )
        )
        return True
    del row["resume"]
    warn(
        message=(
            "cleared retired plan-file resume override with no recorded epic "
            f"for {repo}::{topic}"
        )
    )
    return True


def _normalize_rows(*, rows: list[dict[str, object]]) -> bool:
    changed = False
    for row in rows:
        if _normalize_resume_override(row=row):
            changed = True
    return changed


def _read_rows(*, store_path: str | os.PathLike[str] | None = None) -> list[dict[str, object]]:
    """Read the mapping store as raw dicts, skipping (and naming) bad lines.

    Operating on raw dicts (not Tracks) for rewrite/remove preserves unknown
    keys such as ``added_at`` on the surviving rows.
    """
    path = resolve_store(store_path=store_path)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    # ValueError covers the UnicodeDecodeError a non-UTF-8 store raises; it is a
    # ValueError subclass, so an OSError-only handler leaked it (B7).
    except (OSError, ValueError) as exc:  # PermissionError, NFS hiccup, mid-move, non-UTF-8
        warn(message=f"unreadable mapping store {path}: {exc}")
        return []
    rows: list[dict[str, object]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            warn(message=f"skipping malformed line {lineno} in {path}: {exc}")
            continue
        record = jsonio.as_object(value=obj)
        if record is None:
            warn(message=f"skipping non-object line {lineno} in {path}")
            continue
        rows.append(record)
    return rows


def _write_rows(
    *,
    rows: Iterable[dict[str, object]],
    store_path: str | os.PathLike[str] | None = None,
) -> None:
    body = "".join(json.dumps(row) + "\n" for row in rows)
    atomic_write(path=resolve_store(store_path=store_path), body=body)


def _track_from_row(*, row: dict[str, object]) -> Track | None:
    """Build a mapped Track from a raw row, or None (naming the offender)."""
    topic = row.get("topic")
    repo = row.get("repo")
    if not isinstance(topic, str) or not isinstance(repo, str):
        warn(message=f"skipping row missing topic/repo: {row!r}")
        return None
    # A per-track override is present ONLY if the row carries an int
    # ``ctx_threshold``; a missing (or non-int) value means "no override" → None,
    # so the daemon-wide default applies. Do NOT default to DEFAULT_CTX_THRESHOLD
    # at read time — that would make a bare row indistinguishable from a row that
    # pinned the current default, defeating the daemon-wide ``--warn-percent``.
    threshold = row.get("ctx_threshold")
    ctx_threshold = threshold if isinstance(threshold, int) else None

    def _opt_str(*, key: str) -> str | None:
        value = row.get(key)
        return value if isinstance(value, str) else None

    return Track(
        topic=topic,
        repo=repo,
        tmux=_opt_str(key="tmux"),
        resume=_opt_str(key="resume"),
        epic=_opt_str(key="epic"),
        ctx_threshold=ctx_threshold,
        pinned_session_id=_opt_str(key="pinned_session_id"),
        observed_session_identity=_opt_str(key="observed_session_identity"),
        added_at=_opt_str(key="added_at"),
        assigned=True,
    )


def read_mapping(*, store_path: str | os.PathLike[str] | None = None) -> list[Track]:
    """Read the mapping store into typed Tracks (fail-soft on bad rows)."""
    tracks: list[Track] = []
    path = resolve_store(store_path=store_path)
    rows = _read_rows(store_path=store_path)
    if _normalize_rows(rows=rows):
        with file_lock(target=path):
            rows = _read_rows(store_path=store_path)
            _ = _normalize_rows(rows=rows)
            _write_rows(rows=rows, store_path=store_path)
    for row in rows:
        track = _track_from_row(row=row)
        if track is not None:
            tracks.append(track)
    return tracks


def _track_to_row(*, track: Track) -> dict[str, object]:
    # A legacy row's `handoff` key is READ without error (it is simply not mapped onto
    # any Track field) and is dropped here, so the first rewrite that touches such a row
    # retires the key. The store never emits it: a track's read-first source is the plan
    # state held on its ledger `epic`, and a second, path-shaped copy of that answer is
    # exactly the drift the locator replaced.
    row: dict[str, object] = {
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
    _ = _normalize_resume_override(row=row)
    return row


def record_observed_session_identity(
    *,
    repo: str,
    topic: str,
    session_identity: str,
    store_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Persist that this mapped track has been observed with ``session_identity``."""
    repo_norm = norm(repo=repo)
    with file_lock(target=resolve_store(store_path=store_path)):
        rows = _read_rows(store_path=store_path)
        changed = False
        for row in rows:
            row_repo = row.get("repo")
            if (
                isinstance(row_repo, str)
                and norm(repo=row_repo) == repo_norm
                and row.get("topic") == topic
                and row.get("observed_session_identity") != session_identity
            ):
                row["observed_session_identity"] = session_identity
                changed = True
        if changed:
            _write_rows(rows=rows, store_path=store_path)
        return changed


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
        rows = _read_rows(store_path=store_path)
        kept = [row for row in rows if keep(row=row)]
        if len(kept) != len(rows):
            _write_rows(rows=kept, store_path=store_path)
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
    :func:`_write_rows`).
    """
    repo_norm = norm(repo=repo)
    with file_lock(target=resolve_store(store_path=store_path)):
        rows = _read_rows(store_path=store_path)
        changed = False
        for row in rows:
            row_repo = row.get("repo")
            if (
                isinstance(row_repo, str)
                and norm(repo=row_repo) == repo_norm
                and row.get("topic") == topic
                and row.get("tmux") != new_tmux
            ):
                row["tmux"] = new_tmux
                changed = True
        if changed:
            _write_rows(rows=rows, store_path=store_path)
        return changed
