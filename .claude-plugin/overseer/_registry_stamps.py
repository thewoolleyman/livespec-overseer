"""The injection-stamp sidecar — per-track round timestamps, bands, resume-pending.

Extracted from `registry.py` at its own section banner when that module crossed the
250-LLOC hard ceiling. This is the timestamp the restart-authorization check compares
the `.overseer-state` file's mtime against (a `ready` must be THIS round's).
`registry.py` re-exports this surface, so consumers keep importing `registry`.
"""

from __future__ import annotations

import json
import os

import jsonio
from _registry_core import (
    atomic_write,
    file_lock,
    resolve_stamp_store,
)
from _registry_stamp_core import read_stamp_data, stamp_key
from _registry_stamp_resume import read_resume_pending, set_resume_pending

__all__: list[str] = [
    "add_notified_band",
    "clear_injection_stamp",
    "read_injection_stamp",
    "read_launch_statusline_baseline",
    "read_notified_bands",
    "read_post_respawn",
    "read_resume_pending",
    "record_launch_statusline_baseline",
    "record_post_respawn",
    "set_resume_pending",
    "write_injection_stamp",
]


def read_injection_stamp(
    *,
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
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    value = data.get(stamp_key(repo=repo, topic=topic))
    if value is None:
        return None
    entry = jsonio.as_object(value=value)
    if entry is not None:
        at = entry.get("at")
        if at is None:
            return None
        stamped = jsonio.as_float(value=at)
        if stamped is None:
            _warn_non_numeric_stamp(repo=repo, topic=topic)
        return stamped
    # Legacy bare-float value, from before the sidecar grew its dict shape.
    stamped = jsonio.as_float(value=value)
    if stamped is None:
        _warn_non_numeric_stamp(repo=repo, topic=topic)
    return stamped


def _warn_non_numeric_stamp(*, repo: str, topic: str) -> None:
    from _registry_core import warn

    warn(message=f"non-numeric injection stamp for {repo}::{topic}")


def write_injection_stamp(
    *,
    repo: str,
    topic: str,
    ts: float,
    session_identity: str | None = None,
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
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        identity = session_identity or f"claude:{topic}:{topic}"
        entry: dict[str, object] = {
            "at": float(ts),
            "bands": [],
            "session_identity": identity,
        }
        data[stamp_key(repo=repo, topic=topic)] = entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_notified_bands(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> list[int]:
    """The escalation bands already notified this round for a track.

    Reads the ``bands`` member of the dict-shaped sidecar value. Empty for a
    legacy bare-float value, an absent key, or an unusable value — so a track with
    no recorded bands is treated as "nothing notified yet".
    """
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    value = data.get(stamp_key(repo=repo, topic=topic))
    entry = jsonio.as_object(value=value)
    if entry is None:
        return []
    bands = jsonio.as_list(value=entry.get("bands"))
    if bands is None:
        return []
    return [b for b in bands if isinstance(b, int)]


def add_notified_band(
    *,
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
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        value = data.get(key)
        existing = jsonio.as_object(value=value)
        if existing is not None:
            entry: dict[str, object] = dict(existing)  # preserve at + existing bands
        elif value is None:
            entry = {}
        else:
            # Legacy bare-float value: upgrade it to the dict shape, keeping `at`.
            legacy = jsonio.as_float(value=value)
            entry = {} if legacy is None else {"at": legacy}
        bands_raw = jsonio.as_list(value=entry.get("bands"))
        bands = [b for b in bands_raw if isinstance(b, int)] if bands_raw is not None else []
        if band not in bands:
            bands.append(band)
        entry["bands"] = bands
        data[key] = entry
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def clear_injection_stamp(
    *,
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
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        if key in data:
            del data[key]
            atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_launch_statusline_baseline(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> str | None:
    """Return the launch-time rendered model baseline when ``overseer start`` recorded one."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    entry = jsonio.as_object(value=data.get(stamp_key(repo=repo, topic=topic)))
    if entry is None:
        return None
    baseline = entry.get("launch_statusline_model")
    return baseline if isinstance(baseline, str) else None


def record_launch_statusline_baseline(
    *,
    repo: str,
    topic: str,
    model: str | None,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Record the rendered model immediately after an overseer-started launch."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        current["launch_statusline_model"] = model
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_post_respawn(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> tuple[int, str] | None:
    """Return the post-respawn baseline ``(ctx, resume)`` when recorded."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    entry = jsonio.as_object(value=data.get(stamp_key(repo=repo, topic=topic)))
    post_respawn = jsonio.as_object(value=entry.get("post_respawn")) if entry else None
    if post_respawn is None:
        return None
    ctx = post_respawn.get("ctx")
    resume = post_respawn.get("resume")
    if not isinstance(ctx, int) or not isinstance(resume, str):
        return None
    return ctx, resume


def record_post_respawn(
    *,
    repo: str,
    topic: str,
    ctx: int | None,
    resume: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Record the fresh session's no-work baseline after a successful respawn."""
    if ctx is None:
        return
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        current["post_respawn"] = {"ctx": ctx, "resume": resume}
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
