"""The injection-stamp sidecar — per-track round timestamps, bands, resume-pending.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. This is the timestamp the restart-authorization check compares
the `.overseer-state` file's mtime against (a `ready` must be THIS round's).
`registry.py` re-exports this surface, so consumers keep importing `registry`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import jsonio
from _registry_core import (
    atomic_write,
    file_lock,
    norm,
    resolve_stamp_store,
    warn,
)

__all__: list[str] = [
    "add_notified_band",
    "clear_injection_stamp",
    "read_injection_stamp",
    "read_notified_bands",
    "read_resume_pending",
    "set_resume_pending",
    "write_injection_stamp",
]


def _stamp_key(repo: str, topic: str) -> str:
    return f"{norm(repo)}\t{topic}"


def _read_stamp_data(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    # ValueError subsumes BOTH json.JSONDecodeError and the UnicodeDecodeError a
    # non-UTF-8 sidecar raises.
    except (OSError, ValueError) as exc:
        warn(f"unreadable injection-stamp sidecar {path}: {exc}")
        return {}
    stamp = jsonio.as_object(data)
    if stamp is None:
        warn(f"injection-stamp sidecar {path} is not a JSON object")
        return {}
    return stamp


def read_injection_stamp(
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> float | None:
    """Read a track's injection-round timestamp (epoch seconds), or None if unset.

    The per-key sidecar value is the dict shape ``{"at": <float>, "bands": [...]}``
    — this returns the ``at`` member (the round-open timestamp the certification
    check compares a ready marker's mtime against). BACK-COMPAT: a legacy bare
    float value (the pre-escalation shape) is still accepted and returned as-is.
    None if the key is absent, the dict lacks an ``at``, or the value is unusable.
    """
    data = _read_stamp_data(resolve_stamp_store(stamp_path))
    value = data.get(_stamp_key(repo, topic))
    if value is None:
        return None
    entry = jsonio.as_object(value)
    if entry is not None:
        at = entry.get("at")
        if at is None:
            return None
        stamped = jsonio.as_float(at)
        if stamped is None:
            warn(f"non-numeric injection stamp for {repo}::{topic}")
        return stamped
    # Legacy bare-float value, from before the sidecar grew its dict shape.
    stamped = jsonio.as_float(value)
    if stamped is None:
        warn(f"non-numeric injection stamp for {repo}::{topic}")
    return stamped


def write_injection_stamp(
    repo: str,
    topic: str,
    ts: float,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Open a fresh injection round for a track: stamp ``at`` and RESET its bands.

    Sets the per-key value to ``{"at": float(ts), "bands": []}`` — a NEW round, so
    any previously-notified escalation bands are cleared (a genuinely fresh round
    must be able to re-warn every band). Read-modify-write under the stamp-sidecar
    lock (so a concurrent writer cannot lose another track's value — B6) and via an
    atomic replace (so a crash cannot truncate the sidecar — B6). Fail-soft on
    OSError (B7).
    """
    path = resolve_stamp_store(stamp_path)
    with file_lock(path):
        data = _read_stamp_data(path)
        data[_stamp_key(repo, topic)] = {"at": float(ts), "bands": []}
        atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_notified_bands(
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> list[int]:
    """The escalation bands already notified this round for a track.

    Reads the ``bands`` member of the dict-shaped sidecar value. Empty for a
    legacy bare-float value, an absent key, or an unusable value — so a track with
    no recorded bands is treated as "nothing notified yet".
    """
    data = _read_stamp_data(resolve_stamp_store(stamp_path))
    value = data.get(_stamp_key(repo, topic))
    entry = jsonio.as_object(value)
    if entry is None:
        return []
    bands = jsonio.as_list(entry.get("bands"))
    if bands is None:
        return []
    return [b for b in bands if isinstance(b, int)]


def add_notified_band(
    repo: str,
    topic: str,
    band: int,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Record ``band`` as notified this round (idempotent; preserves ``at``).

    Read-modify-write under the same stamp-sidecar lock + atomic replace as
    :func:`write_injection_stamp`. If the current value is a legacy bare float, it
    is upgraded to the dict shape with that float preserved as ``at``; if it is
    already a dict, its ``at`` (and any existing bands) are preserved. Appending an
    already-recorded band is a no-op (idempotent). Fail-soft on OSError (B7).
    """
    path = resolve_stamp_store(stamp_path)
    with file_lock(path):
        data = _read_stamp_data(path)
        key = _stamp_key(repo, topic)
        value = data.get(key)
        existing = jsonio.as_object(value)
        if existing is not None:
            entry: dict[str, object] = dict(existing)  # preserve at + existing bands
        elif value is None:
            entry = {}
        else:
            # Legacy bare-float value: upgrade it to the dict shape, keeping `at`.
            legacy = jsonio.as_float(value)
            entry = {} if legacy is None else {"at": legacy}
        bands_raw = jsonio.as_list(entry.get("bands"))
        bands = [b for b in bands_raw if isinstance(b, int)] if bands_raw is not None else []
        if band not in bands:
            bands.append(band)
        entry["bands"] = bands
        data[key] = entry
        atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def clear_injection_stamp(
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Delete a track's injection stamp, closing out its certification round.

    Called by the daemon when it restarts a track: without this the persisted
    stamp OUTLIVES the round, degrading the "marker mtime > injection stamp"
    interlock to "marker newer than the FIRST-EVER injection" — so a later,
    round-less marker (a handoff convention, or a forged one) would spuriously
    certify (adversarial code review 2026-07-13, blocker B4). Same lock + atomic
    write as :func:`write_injection_stamp`; a no-op if the stamp is absent.
    """
    path = resolve_stamp_store(stamp_path)
    with file_lock(path):
        data = _read_stamp_data(path)
        if _stamp_key(repo, topic) in data:
            del data[_stamp_key(repo, topic)]
            atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_resume_pending(
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

    Round-scoped by construction: :func:`clear_injection_stamp` (restart closed) deletes
    the whole key and :func:`write_injection_stamp` (a fresh round) overwrites the dict, so
    the flag can never outlive the round it belongs to. Fail-soft: an unusable value ⇒ False.
    """
    data = _read_stamp_data(resolve_stamp_store(stamp_path))
    value = data.get(_stamp_key(repo, topic))
    entry = jsonio.as_object(value)
    if entry is None:
        return False
    return entry.get("resume_pending") is True


def set_resume_pending(
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Record that a restart respawned the fresh session but its resume did not submit.

    Sets the ``resume_pending`` member on the track's injection-stamp dict, PRESERVING
    ``at`` (so the ``ready`` marker still certifies — ``mtime > at``) and any notified
    ``bands``. Same lock + atomic replace as :func:`write_injection_stamp`. If the current
    value is a legacy bare float, it is upgraded to the dict shape with that float as
    ``at``; if the key is absent, a bare ``{"resume_pending": True}`` is written (the
    retry still fires — it keys on this flag, not on ``at``). Fail-soft on OSError (B7).
    """
    path = resolve_stamp_store(stamp_path)
    with file_lock(path):
        data = _read_stamp_data(path)
        key = _stamp_key(repo, topic)
        value = data.get(key)
        existing = jsonio.as_object(value)
        if existing is not None:
            entry: dict[str, object] = dict(existing)  # preserve at + bands
        elif value is None:
            entry = {}
        else:
            # Legacy bare-float value: upgrade it to the dict shape, keeping `at`.
            legacy = jsonio.as_float(value)
            entry = {} if legacy is None else {"at": legacy}
        entry["resume_pending"] = True
        data[key] = entry
        atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
