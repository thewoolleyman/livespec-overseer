"""Durable authorization boundary for a ready-declared Herdr replacement."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import herdr_identity
import registry
import signals
from _supervisor_launch_profile import ClaudeLaunchPlan

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["begin_herdr_replacement"]

_RECORD_NAME = ".herdr-replacement.json"
_LOCK_NAME = ".herdr-replacement.lock"


class ProcessObservation(Protocol):
    pid: int
    starttime: str
    executable: str
    argv: Sequence[str]
    process_group: int
    session_id: int


class ReplacementSnapshot(Protocol):
    shell: ProcessObservation
    foreground_group: int
    processes: Sequence[ProcessObservation]


class ReplacementResult(Protocol):
    ok: bool
    error: str


class ReplacementPane(Protocol):
    def herdr_replacement_snapshot(self, *, session: str) -> ReplacementSnapshot: ...

    def herdr_terminate(self, *, session: str, process_group: int) -> ReplacementResult: ...


def _scratch_path(*, track: registry.Track) -> Path:
    return Path(track.repo) / "tmp" / "overseer" / track.topic


@contextmanager
def _transaction_lock(*, path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def _durable_write(*, path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        _ = handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    _ = temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _predecessor(*, snapshot: ReplacementSnapshot, identity: str) -> ProcessObservation:
    _, pid_text, starttime, _ = identity.split(":", 3)
    pid = int(pid_text)
    return next(
        process
        for process in snapshot.processes
        if process.pid == pid and process.starttime == starttime
    )


def _process_record(*, process: ProcessObservation) -> dict[str, object]:
    return {
        "pid": process.pid,
        "starttime": process.starttime,
        "executable": process.executable,
        "argv": list(process.argv),
        "process_group": process.process_group,
        "session_id": process.session_id,
    }


def _record(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    launch: ClaudeLaunchPlan,
    snapshot: ReplacementSnapshot,
) -> dict[str, object]:
    decoded = herdr_identity.decode_target(value=target)
    server = cast(herdr_identity.HerdrPaneTarget, decoded.herdr)
    round_record = registry.read_round_record(
        repo=track.repo,
        topic=track.topic,
        stamp_path=sup.stamp_path,
    )
    declared = cast(signals.TrackState, signals.read_state(repo=track.repo, topic=track.topic))
    identity = cast(str, round_record.session_identity)
    predecessor = _predecessor(snapshot=snapshot, identity=identity)
    return {
        "version": 1,
        "phase": "before-stop",
        "target": target,
        "server": {
            "socket_path": server.socket_path,
            "pid": server.server_pid,
            "starttime": server.server_starttime,
            "pane_id": server.pane_id,
        },
        "runtime": "claude",
        "predecessor": {
            "pid": predecessor.pid,
            "starttime": predecessor.starttime,
            "process_group": snapshot.foreground_group,
        },
        "shell": _process_record(process=snapshot.shell),
        "round": {
            "ready_mtime": declared.mtime,
            "round_at": round_record.at,
            "session_identity": identity,
        },
        "launch": {
            "command": launch.command,
            "cwd": track.repo,
            "env": dict(launch.env),
        },
    }


def begin_herdr_replacement(
    *, sup: Supervisor, track: registry.Track, target: str, launch: ClaudeLaunchPlan
) -> None:
    """Fence the ready authorization durably, then make its one stop attempt."""
    pane = cast(ReplacementPane, sup.tmux)
    scratch = _scratch_path(track=track)
    with _transaction_lock(path=scratch / _LOCK_NAME):
        snapshot = pane.herdr_replacement_snapshot(session=target)
        transaction = _record(
            sup=sup,
            track=track,
            target=target,
            launch=launch,
            snapshot=snapshot,
        )
        _durable_write(path=scratch / _RECORD_NAME, value=transaction)
        transaction["phase"] = "signal-attempted"
        _durable_write(path=scratch / _RECORD_NAME, value=transaction)
        predecessor = cast(dict[str, object], transaction["predecessor"])
        _ = pane.herdr_terminate(
            session=target,
            process_group=cast(int, predecessor["process_group"]),
        )
