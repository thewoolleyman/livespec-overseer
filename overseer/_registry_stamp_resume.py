"""Resume-pending state in the injection-stamp sidecar."""

from __future__ import annotations

import json
import os

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = ["read_resume_pending", "set_resume_pending"]


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


def set_resume_pending(
    *,
    repo: str,
    topic: str,
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
        data[key] = entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
