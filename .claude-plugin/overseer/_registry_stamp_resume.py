"""Resume-pending state in the injection-stamp sidecar."""

from __future__ import annotations

import json
import os

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = [
    "add_resume_retry_attempts",
    "read_resume_pending",
    "read_resume_pending_identity",
    "read_resume_retry_attempts",
    "set_resume_pending",
]


def read_resume_pending(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> bool:
    """True if a restart RESPAWNED the fresh session but its resume line never SUBMITTED.

    The daemon's restart respawns the pane and pastes the ``read <handoff> and follow
    it`` resume line, but a freshly-respawned TUI can DROP the Enter while still drawing
    its welcome screen — leaving the fresh session live but idle with the resume line
    un-submitted (proven live 2026-07-17: fabro / autonomous-mode / overseer-rewrite all
    stranded this way in one day). ``set_resume_pending`` records that state as a
    round-scoped member of the injection-stamp dict so the NEXT tick retries the SUBMIT
    ONLY (re-send Enter, never a re-respawn — a fresh ``ready`` is the sole respawn
    trigger). Reads the ``resume_pending`` member; anything else ⇒ False.

    Round-scoped by construction: ``clear_injection_stamp`` (restart closed) deletes
    the whole key and ``write_injection_stamp`` (a fresh round) overwrites the dict, so
    the flag can never outlive the round it belongs to. Fail-soft: an unusable value ⇒
    False.
    """
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    value = data.get(stamp_key(repo=repo, topic=topic))
    entry = jsonio.as_object(value=value)
    if entry is None:
        return False
    return entry.get("resume_pending") is True


def read_resume_pending_identity(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """Identity of the session whose pending resume-submit may be retried."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    value = data.get(stamp_key(repo=repo, topic=topic))
    entry = jsonio.as_object(value=value)
    if entry is None or entry.get("resume_pending") is not True:
        return None
    identity = entry.get("resume_pending_session_identity")
    return identity if isinstance(identity, str) and identity else None


def read_resume_retry_attempts(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> int:
    """Enter keystrokes already spent by this resume-pending episode."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    value = data.get(stamp_key(repo=repo, topic=topic))
    entry = jsonio.as_object(value=value)
    if entry is None or entry.get("resume_pending") is not True:
        return 0
    attempts = entry.get("resume_retry_attempts")
    if isinstance(attempts, int) and not isinstance(attempts, bool) and attempts > 0:
        return attempts
    return 0


def add_resume_retry_attempts(
    *,
    repo: str,
    topic: str,
    attempts: int,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Add spent Enter keystrokes to the current resume-pending episode."""
    if attempts <= 0:
        return
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        if entry is None or entry.get("resume_pending") is not True:
            return
        stored = entry.get("resume_retry_attempts")
        current = (
            stored if isinstance(stored, int) and not isinstance(stored, bool) and stored > 0 else 0
        )
        next_entry: dict[str, object] = dict(entry)
        next_entry["resume_retry_attempts"] = current + attempts
        data[key] = next_entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def set_resume_pending(
    *,
    repo: str,
    topic: str,
    session_identity: str | None = None,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Record that a restart respawned the fresh session but its resume did not submit.

    Sets the ``resume_pending`` member on the track's injection-stamp dict, PRESERVING
    ``at`` (so the ``ready`` marker still certifies — ``mtime > at``) and any notified
    ``bands``. Same lock + atomic replace as ``write_injection_stamp``. If the current
    value is a legacy bare float, it is upgraded to the dict shape with that float as
    ``at``; if the key is absent, a bare ``{"resume_pending": True}`` is written (the
    retry still fires — it keys on this flag, not on ``at``). Fail-soft on OSError (B7).
    """
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        value = data.get(key)
        existing = jsonio.as_object(value=value)
        if existing is not None:
            entry: dict[str, object] = dict(existing)  # preserve at + bands
        elif value is None:
            entry = {}
        else:
            # Legacy bare-float value: upgrade it to the dict shape, keeping `at`.
            legacy = jsonio.as_float(value=value)
            entry = {} if legacy is None else {"at": legacy}
        entry["resume_pending"] = True
        entry["resume_retry_attempts"] = 0
        if session_identity is not None:
            entry["resume_pending_session_identity"] = session_identity
        data[key] = entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
