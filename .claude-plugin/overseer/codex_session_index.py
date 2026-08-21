"""Codex session-index readers and dead-session rollout lookup."""

from __future__ import annotations

import os
from pathlib import Path

import jsonio

__all__: list[str] = [
    "latest_session_for_thread_name",
    "read_thread_names",
    "rollout_exists",
]


def read_index_final(*, codex_home: str | os.PathLike[str]) -> dict[str, tuple[str, str]]:
    """``session_index.jsonl`` folded to ``{session id: (thread_name, updated_at)}``.

    The index is an APPEND log — a renamed thread appends a fresh record for the SAME id, so
    the LAST record for an id gives its final ``thread_name`` + ``updated_at`` (``""`` when
    the field is missing). The one, shared parser behind :func:`read_thread_names` (adoption)
    and :func:`latest_session_for_thread_name` (reboot recovery) so the two cannot drift.
    Fail-soft throughout: a missing file, an UNDECODABLE file, an unparsable line, or a
    record missing a usable id/name is skipped, never raised. The undecodable case was
    claimed by this docstring before it was true — a non-UTF-8 index raised
    ``UnicodeDecodeError`` straight through the ``OSError``-only handler below.
    """
    out: dict[str, tuple[str, str]] = {}
    try:
        raw = (Path(codex_home) / "session_index.jsonl").read_text(encoding="utf-8")
    # ValueError covers the UnicodeDecodeError a non-UTF-8 index raises, which the
    # docstring's fail-soft promise above did not actually hold for.
    except (OSError, ValueError):
        return out
    for line in raw.splitlines():
        parsed = jsonio.parse_object_line(line=line)
        if jsonio.is_parse_failure(result=parsed):
            continue
        record = parsed.unwrap()
        if record is None:
            continue
        session_id, name = record.get("id"), record.get("thread_name")
        updated = record.get("updated_at")
        if isinstance(session_id, str) and isinstance(name, str) and session_id and name:
            out[session_id] = (name, updated if isinstance(updated, str) else "")
    return out


def read_thread_names(*, codex_home: str | os.PathLike[str]) -> dict[str, str]:
    """``session_index.jsonl`` as ``{session id: thread_name}`` (last record per id wins)."""
    return {sid: name for sid, (name, _updated) in read_index_final(codex_home=codex_home).items()}


def latest_session_for_thread_name(
    *, thread_name: str, codex_home: str | os.PathLike[str]
) -> str | None:
    """The session id of the most-recently-updated indexed session named ``thread_name``.

    Reverses ``session_index.jsonl`` — which SURVIVES the session's death, unlike the live
    rollout fd a running codex holds open — so reboot recovery can learn a DEAD codex track's
    session id from its plan topic (the ``thread_name``). Among ids whose final name matches,
    the one with the greatest ``updated_at`` wins (RFC3339 UTC strings, lexicographically
    ordered, and distinct per id in real index data — verified live 2026-07-18, so the pick is
    unambiguous). Returns None when the topic names no indexed session — the caller treats such
    a track as Claude. Fail-soft: a missing/unreadable index yields None.
    """
    matches = [
        (updated, sid)
        for sid, (name, updated) in read_index_final(codex_home=codex_home).items()
        if name == thread_name
    ]
    return max(matches)[1] if matches else None


def rollout_exists(*, session_id: str, codex_home: str | os.PathLike[str]) -> bool:
    """True if a rollout file for ``session_id`` still exists under ``<codex_home>/sessions``.

    A rollout is ``rollout-<iso-ts>-<session id>.jsonl``, nested under ``sessions/YYYY/MM/DD/``
    (verified live). A dead session's rollout persists on disk, and its presence is what
    ``codex resume`` needs to reattach — so reboot recovery gates option (c) on it: rollout
    present ⇒ ``codex resume <id>`` can reattach the SAME conversation; rollout gone ⇒ recovery
    falls back to skip+surface (option b) rather than mis-recreating the track as Claude
    (which would orphan the rollout). The ``session_id`` is a UUID (no glob metacharacters), so
    it is safe to interpolate into the pattern. Fail-soft to False.
    """
    sessions = Path(codex_home) / "sessions"
    try:
        return any(sessions.rglob(f"rollout-*-{session_id}.jsonl"))
    except OSError:
        return False
