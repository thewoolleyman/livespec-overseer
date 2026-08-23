"""Durable shell-only attention episodes in the injection-stamp sidecar."""

from __future__ import annotations

import json
import os

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = [
    "clear_shell_episode",
    "read_shell_episode",
    "record_shell_episode",
]


def read_shell_episode(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> float | None:
    """Return the durable shell-only episode start time, if present and usable."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    entry = jsonio.as_object(value=data.get(stamp_key(repo=repo, topic=topic)))
    if entry is None:
        return None
    return jsonio.as_float(value=entry.get("shell_episode_since"))


def record_shell_episode(
    *,
    repo: str,
    topic: str,
    since: float,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Persist the first-observed time for a shell-only attention episode."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        if "shell_episode_since" not in current:
            current["shell_episode_since"] = float(since)
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")


def clear_shell_episode(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Clear the durable shell-only episode without touching round data."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        if entry is None or "shell_episode_since" not in entry:
            return
        current = dict(entry)
        del current["shell_episode_since"]
        if current:
            data[key] = current
        else:
            del data[key]
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
