"""Stable Linux process generations used by native Herdr replacement."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_STARTTIME_INDEX = 19

__all__: list[str] = [
    "ObservedProcess",
    "ProcessIds",
    "ProcessReader",
    "proc_process",
    "proc_process_ids",
]


@dataclass(frozen=True, kw_only=True)
class ObservedProcess:
    """One process generation as the kernel reports it."""

    pid: int
    starttime: str
    executable: str
    argv: tuple[str, ...]
    process_group: int
    session_id: int


class ProcessReader(Protocol):
    def __call__(self, *, pid: int) -> ObservedProcess | None: ...


class ProcessIds(Protocol):
    def __call__(self) -> Sequence[int]: ...


def _stat_fields(*, pid: int) -> tuple[int, int, str] | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    _, separator, tail = raw.rpartition(")")
    fields = tail.strip().split()
    if not separator or len(fields) <= _STARTTIME_INDEX:
        return None
    try:
        process_group = int(fields[2])
        session_id = int(fields[3])
    except ValueError:
        return None
    starttime = fields[_STARTTIME_INDEX]
    if process_group <= 0 or session_id <= 0 or not starttime:
        return None
    return process_group, session_id, starttime


def _executable(*, pid: int) -> str | None:
    try:
        return str(Path(f"/proc/{pid}/exe").readlink().resolve())
    except OSError:
        return None


def _argv(*, pid: int) -> tuple[str, ...] | None:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return None
    parts = tuple(
        item.decode("utf-8", errors="surrogateescape") for item in raw.split(b"\0") if item
    )
    return parts or None


def proc_process(*, pid: int) -> ObservedProcess | None:
    """Read one stable process image twice around executable and argv evidence."""
    before = _stat_fields(pid=pid)
    executable_before = _executable(pid=pid)
    argv = _argv(pid=pid)
    executable_after = _executable(pid=pid)
    after = _stat_fields(pid=pid)
    if (
        before is None
        or before != after
        or executable_before is None
        or executable_before != executable_after
        or argv is None
    ):
        return None
    process_group, session_id, starttime = before
    return ObservedProcess(
        pid=pid,
        starttime=starttime,
        executable=executable_before,
        argv=argv,
        process_group=process_group,
        session_id=session_id,
    )


def proc_process_ids() -> tuple[int, ...]:
    """Enumerate the process table without treating unreadable entries as processes."""
    try:
        entries = tuple(Path("/proc").iterdir())
    except OSError:
        return ()
    return tuple(sorted(int(entry.name) for entry in entries if entry.name.isdigit()))
