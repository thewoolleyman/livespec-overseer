"""Event-driven wait for supervised session state declarations.

The daemon's authority still lives entirely in :func:`Supervisor.tick` and the
normal ``evaluate`` cascade. This module only shortens the inter-tick wait when a
session writes its out-of-band state file, so the existing ready certification,
busy, settle, identity, and restart gates run sooner.
"""

from __future__ import annotations

import ctypes
import os
import select
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import _supervisor_discovery
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["wait_for_state_declaration"]

_STATE_POLL_SECONDS = 0.2
_IN_ACCESS_MASK = 0x0000_0001
_IN_MODIFY_MASK = 0x0000_0002
_IN_ATTRIB_MASK = 0x0000_0004
_IN_CLOSE_WRITE_MASK = 0x0000_0008
_IN_MOVED_TO_MASK = 0x0000_0080
_IN_CREATE_MASK = 0x0000_0100
_IN_DELETE_SELF_MASK = 0x0000_0400
_IN_MOVE_SELF_MASK = 0x0000_0800
_IN_IGNORED_MASK = 0x0000_8000
_IN_NONBLOCK = 0o0004000
_IN_CLOEXEC = 0o2000000
_EVENT_MASK = (
    _IN_ACCESS_MASK
    | _IN_MODIFY_MASK
    | _IN_ATTRIB_MASK
    | _IN_CLOSE_WRITE_MASK
    | _IN_MOVED_TO_MASK
    | _IN_CREATE_MASK
    | _IN_DELETE_SELF_MASK
    | _IN_MOVE_SELF_MASK
    | _IN_IGNORED_MASK
)


def _state_paths(*, sup: Supervisor) -> list[Path]:
    paths: list[Path] = []
    seen: set[tuple[str, str]] = set()
    repos = _supervisor_discovery.resolve_watch(sup=sup)
    discovered = registry.discover_plans(watch_repos=repos)
    mapped = [
        (track.repo, track.topic) for track in registry.read_mapping(store_path=sup.store_path)
    ]
    for repo, topic in [*discovered, *mapped]:
        key = (registry.norm(repo=repo), topic)
        if key in seen or not registry.repo_root_present(repo=repo):
            continue
        seen.add(key)
        paths.append(signals.state_path(repo=repo, topic=topic))
    return paths


def _watch_roots(*, paths: list[Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        for root in (path.parent.parent, path.parent):
            if root in seen:
                continue
            seen.add(root)
            roots.append(root)
    return roots


def _snapshot(*, paths: list[Path]) -> dict[Path, tuple[int, int] | None]:
    values: dict[Path, tuple[int, int] | None] = {}
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            values[path] = None
        else:
            values[path] = (stat.st_mtime_ns, stat.st_size)
    return values


def _state_changed(
    *,
    paths: list[Path],
    before: dict[Path, tuple[int, int] | None],
) -> bool:
    return _snapshot(paths=paths) != before


def _inotify_fd() -> int | None:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fd = libc.inotify_init1(_IN_NONBLOCK | _IN_CLOEXEC)
    except (AttributeError, OSError):
        return None
    if fd < 0:
        return None
    return fd


def _add_inotify_watch(*, fd: int, root: Path) -> None:
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    libc = ctypes.CDLL(None, use_errno=True)
    encoded = os.fsencode(root)
    _ = libc.inotify_add_watch(fd, encoded, _EVENT_MASK)


def _drain_inotify(*, fd: int) -> None:
    while True:
        try:
            _ = os.read(fd, 4096)
        except BlockingIOError:
            return
        except OSError:
            return


def _wait_with_inotify(
    *,
    fd: int,
    paths: list[Path],
    before: dict[Path, tuple[int, int] | None],
    deadline: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> bool:
    while True:
        if _state_changed(paths=paths, before=before):
            return True
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        timeout = min(_STATE_POLL_SECONDS, remaining)
        ready, _, _ = select.select([fd], [], [], timeout)
        if ready:
            _drain_inotify(fd=fd)
        else:
            sleep(0.0)


def _wait_with_polling(
    *,
    paths: list[Path],
    before: dict[Path, tuple[int, int] | None],
    deadline: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> bool:
    while True:
        if _state_changed(paths=paths, before=before):
            return True
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        sleep(min(_STATE_POLL_SECONDS, remaining))


def wait_for_state_declaration(*, sup: Supervisor, interval: float) -> bool:
    """Wait up to ``interval`` seconds, returning early when a state file changes."""
    paths = _state_paths(sup=sup)
    if interval <= 0 or not paths:
        sup.sleep(interval)
        return False
    before = _snapshot(paths=paths)
    monotonic = time.monotonic
    deadline = monotonic() + interval
    fd = _inotify_fd()
    if fd is None:
        return _wait_with_polling(
            paths=paths,
            before=before,
            deadline=deadline,
            monotonic=monotonic,
            sleep=sup.sleep,
        )
    try:
        for root in _watch_roots(paths=paths):
            _add_inotify_watch(fd=fd, root=root)
        return _wait_with_inotify(
            fd=fd,
            paths=paths,
            before=before,
            deadline=deadline,
            monotonic=monotonic,
            sleep=sup.sleep,
        )
    finally:
        os.close(fd)
