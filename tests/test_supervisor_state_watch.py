"""Coverage for the state-file event wait used by the daemon loop."""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from overseer import registry
from overseer.test_supervisor_builders import make_plan, mapped_track

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "overseer" / "_supervisor_state_watch.py"


def _state_watch() -> Any:
    assert MODULE_PATH.is_file()
    return importlib.import_module("_supervisor_state_watch")


@dataclass(kw_only=True)
class WatchSup:
    store_path: str | os.PathLike[str] | None = None
    watch_repos: list[str] | None = None
    watch_set_path: str | os.PathLike[str] | None = None
    slept: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def test_state_paths_union_discovery_and_mapping_without_duplicates(*, tmp_path: Path) -> None:
    state_watch = _state_watch()
    repo, topic = make_plan(tmp_path=tmp_path)
    missing_repo = tmp_path / "missing"
    store = tmp_path / "map.jsonl"
    registry.append_mapping(
        track=mapped_track(repo=repo, topic=topic, session="topic"),
        store_path=store,
    )
    registry.append_mapping(
        track=mapped_track(repo=missing_repo, topic="missing", session="missing"),
        store_path=store,
    )
    sup = WatchSup(store_path=store, watch_repos=[str(repo)])

    assert state_watch._state_paths(sup=sup) == [
        state_watch.signals.state_path(repo=str(repo), topic=topic)
    ]


def test_snapshot_state_change_and_watch_roots_cover_absent_and_existing_paths(
    *, tmp_path: Path
) -> None:
    state_watch = _state_watch()
    state = tmp_path / "tmp" / "overseer" / "topic" / ".overseer-state"
    before = state_watch._snapshot(paths=[state])

    state.parent.mkdir(parents=True)
    state.write_text("ready\n", encoding="utf-8")

    assert before == {state: None}
    assert state_watch._state_changed(paths=[state], before=before) is True
    assert state_watch._watch_roots(paths=[state, state]) == [state.parent.parent, state.parent]


def test_inotify_fd_handles_missing_negative_and_successful_libc(*, monkeypatch) -> None:
    state_watch = _state_watch()

    def missing_cdll(*_args: object, **_kwargs: object) -> object:
        raise OSError("missing libc")

    monkeypatch.setattr(state_watch.ctypes, "CDLL", missing_cdll)
    assert state_watch._inotify_fd() is None

    monkeypatch.setattr(
        state_watch.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: SimpleNamespace(inotify_init1=lambda _flags: -1),
    )
    assert state_watch._inotify_fd() is None

    monkeypatch.setattr(
        state_watch.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: SimpleNamespace(inotify_init1=lambda _flags: 42),
    )
    assert state_watch._inotify_fd() == 42


def test_add_inotify_watch_handles_created_and_uncreatable_roots(
    *, tmp_path: Path, monkeypatch
) -> None:
    state_watch = _state_watch()
    watched: list[tuple[int, bytes, int]] = []

    monkeypatch.setattr(
        state_watch.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: SimpleNamespace(
            inotify_add_watch=lambda fd, encoded, mask: watched.append((fd, encoded, mask))
        ),
    )

    root = tmp_path / "ok"
    state_watch._add_inotify_watch(fd=7, root=root)
    assert watched == [(7, os.fsencode(root), state_watch._EVENT_MASK)]

    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    state_watch._add_inotify_watch(fd=7, root=blocker / "child")
    assert watched == [(7, os.fsencode(root), state_watch._EVENT_MASK)]


def test_drain_inotify_stops_on_blocking_and_os_errors(*, monkeypatch) -> None:
    state_watch = _state_watch()
    reads = [b"event"]

    def blocking_read(fd: int, n: int) -> bytes:
        del fd, n
        if reads:
            return reads.pop()
        raise BlockingIOError

    monkeypatch.setattr(state_watch.os, "read", blocking_read)
    state_watch._drain_inotify(fd=3)
    assert reads == []

    monkeypatch.setattr(
        state_watch.os,
        "read",
        lambda _fd, _n: (_ for _ in ()).throw(OSError("closed")),
    )
    state_watch._drain_inotify(fd=3)


def test_wait_with_polling_returns_on_change_and_timeout(*, tmp_path: Path) -> None:
    state_watch = _state_watch()
    state = tmp_path / ".overseer-state"
    before = state_watch._snapshot(paths=[state])
    slept: list[float] = []

    def sleep_and_write(seconds: float) -> None:
        slept.append(seconds)
        state.write_text("ready\n", encoding="utf-8")

    assert (
        state_watch._wait_with_polling(
            paths=[state],
            before=before,
            deadline=10.0,
            monotonic=lambda: len(slept),
            sleep=sleep_and_write,
        )
        is True
    )
    assert slept == [state_watch._STATE_POLL_SECONDS]

    assert (
        state_watch._wait_with_polling(
            paths=[state],
            before=state_watch._snapshot(paths=[state]),
            deadline=0.0,
            monotonic=lambda: 1.0,
            sleep=slept.append,
        )
        is False
    )


def test_wait_with_inotify_drains_ready_fd_and_times_out(*, monkeypatch, tmp_path: Path) -> None:
    state_watch = _state_watch()
    state = tmp_path / ".overseer-state"
    before = state_watch._snapshot(paths=[state])
    changed = [False, True]
    drained: list[int] = []

    monkeypatch.setattr(
        state_watch,
        "_state_changed",
        lambda *, paths, before: changed.pop(0),
    )
    monkeypatch.setattr(state_watch.select, "select", lambda *_args: ([9], [], []))
    monkeypatch.setattr(state_watch, "_drain_inotify", lambda *, fd: drained.append(fd))

    assert (
        state_watch._wait_with_inotify(
            fd=9,
            paths=[state],
            before=before,
            deadline=10.0,
            monotonic=lambda: 0.0,
            sleep=lambda _seconds: None,
        )
        is True
    )
    assert drained == [9]

    monkeypatch.setattr(state_watch, "_state_changed", lambda *, paths, before: False)
    assert (
        state_watch._wait_with_inotify(
            fd=9,
            paths=[state],
            before=before,
            deadline=0.0,
            monotonic=lambda: 1.0,
            sleep=lambda _seconds: None,
        )
        is False
    )


def test_public_wait_uses_sleep_polling_and_inotify_paths(*, monkeypatch, tmp_path: Path) -> None:
    state_watch = _state_watch()
    state = tmp_path / ".overseer-state"
    sup = WatchSup()

    monkeypatch.setattr(state_watch, "_state_paths", lambda *, sup: [])
    assert state_watch.wait_for_state_declaration(sup=sup, interval=3.0) is False
    assert sup.slept == [3.0]

    monkeypatch.setattr(state_watch, "_state_paths", lambda *, sup: [state])
    monkeypatch.setattr(state_watch, "_snapshot", lambda *, paths: {state: None})
    monkeypatch.setattr(state_watch, "_inotify_fd", lambda: None)
    monkeypatch.setattr(
        state_watch,
        "_wait_with_polling",
        lambda **_kwargs: True,
    )
    assert state_watch.wait_for_state_declaration(sup=sup, interval=3.0) is True

    closed: list[int] = []
    monkeypatch.setattr(state_watch, "_inotify_fd", lambda: 11)
    monkeypatch.setattr(state_watch, "_watch_roots", lambda *, paths: [tmp_path])
    monkeypatch.setattr(state_watch, "_add_inotify_watch", lambda *, fd, root: None)
    monkeypatch.setattr(state_watch, "_wait_with_inotify", lambda **_kwargs: False)
    monkeypatch.setattr(state_watch.os, "close", closed.append)

    assert state_watch.wait_for_state_declaration(sup=sup, interval=3.0) is False
    assert closed == [11]
