"""Fresh daemon-process evidence below one tmux pane's retained shell."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import claude_sessions
import daemon_liveness
from _seams import PidToIntList, PidToOptionalBytes, PidToOptionalStr

__all__: list[str] = [
    "MAX_DESCENDANT_PROCESSES",
    "DaemonProcessIdentity",
    "daemon_descendant_command",
    "foreground_daemon_process",
    "is_daemon_argv",
]

# A real daemon is one direct child today.  The wider bound permits ordinary
# launcher wrappers without letting corrupt or cyclic process evidence hold the
# public bootstrap indefinitely.
MAX_DESCENDANT_PROCESSES = 64
_MODULE_ARG_COUNT = 3
_PROCESS_STAT_FIELDS = 20
_RUNTIME_EXECUTABLE = str(Path(sys.executable).resolve())


@dataclass(frozen=True, kw_only=True)
class DaemonProcessIdentity:
    """Fresh identity of the exact daemon process owning a pane's foreground."""

    pid: int
    starttime: str
    executable: str
    argv: tuple[str, ...]
    process_group: int


@dataclass(frozen=True, kw_only=True)
class _ProcessStatus:
    process_group: int
    foreground_group: int
    starttime: str


def is_daemon_argv(*, command: str) -> bool:
    """Whether ``command`` syntactically places a daemon marker in an argument role.

    This legacy string predicate is not authorization. Exact reuse additionally
    binds the process executable to this installed command's interpreter.
    """
    argv = [*command.split(), "", ""]
    return any(
        (
            Path(argv[0]).name == "overseerd",
            argv[1:_MODULE_ARG_COUNT] == ["-m", "overseer.daemon"],
            Path(argv[1]).name == "overseerd",
        )
    )


def _proc_stat(*, pid: int) -> str | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None


def _proc_executable(*, pid: int) -> str | None:
    try:
        return str(Path(f"/proc/{pid}/exe").readlink().resolve(strict=True))
    except OSError:
        return None


def _process_status(*, raw: str | None) -> _ProcessStatus | None:
    fields = raw.rpartition(") ")[2].split() if raw is not None else []
    if len(fields) < _PROCESS_STAT_FIELDS:
        return None
    try:
        return _ProcessStatus(
            process_group=int(fields[2]),
            foreground_group=int(fields[5]),
            starttime=fields[19],
        )
    except ValueError:
        return None


def _daemon_role(*, argv: tuple[str, ...]) -> bool:
    padded = (*argv, "", "")
    return any(
        (
            padded[1:_MODULE_ARG_COUNT] == ("-m", "overseer.daemon"),
            Path(padded[1]).name == "overseerd",
        )
    )


def _daemon_identity(
    *,
    pid: int,
    cmdline_of: PidToOptionalBytes,
    stat_of: PidToOptionalStr,
    executable_of: PidToOptionalStr,
) -> DaemonProcessIdentity | None:
    raw_command = cmdline_of(pid=pid)
    status = _process_status(raw=stat_of(pid=pid))
    executable = executable_of(pid=pid)
    argv = (
        tuple(part.decode(errors="surrogateescape") for part in raw_command.split(b"\0") if part)
        if raw_command is not None
        else ()
    )
    if status is None or executable is None or not argv:
        return None
    try:
        runtime = str(Path(argv[0]).resolve(strict=True))
        resolved_executable = str(Path(executable).resolve(strict=True))
    except OSError:
        return None
    if (
        runtime != resolved_executable
        or runtime != _RUNTIME_EXECUTABLE
        or not _daemon_role(argv=argv)
    ):
        return None
    return DaemonProcessIdentity(
        pid=pid,
        starttime=status.starttime,
        executable=resolved_executable,
        argv=argv,
        process_group=status.process_group,
    )


def foreground_daemon_process(
    *,
    root_pid: int,
    children_of: PidToIntList = claude_sessions.proc_children,
    cmdline_of: PidToOptionalBytes = claude_sessions.proc_cmdline,
    stat_of: PidToOptionalStr = _proc_stat,
    executable_of: PidToOptionalStr = _proc_executable,
    max_processes: int = MAX_DESCENDANT_PROCESSES,
) -> DaemonProcessIdentity | None:
    """Return the fresh exact daemon owning ``root_pid``'s foreground, or None."""
    root_before = _process_status(raw=stat_of(pid=root_pid))
    if root_before is None or root_before.foreground_group <= 0:
        return None
    pending = [root_pid]
    seen: set[int] = set()
    while pending and len(seen) < max_processes:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        first = _daemon_identity(
            pid=pid,
            cmdline_of=cmdline_of,
            stat_of=stat_of,
            executable_of=executable_of,
        )
        if first is not None and first.process_group == root_before.foreground_group:
            second = _daemon_identity(
                pid=pid,
                cmdline_of=cmdline_of,
                stat_of=stat_of,
                executable_of=executable_of,
            )
            root_after = _process_status(raw=stat_of(pid=root_pid))
            if first == second and root_before == root_after:
                return first
        pending.extend(children_of(pid=pid))
    return None


def daemon_descendant_command(
    *,
    root_pid: int,
    children_of: PidToIntList = claude_sessions.proc_children,
    cmdline_of: PidToOptionalBytes = claude_sessions.proc_cmdline,
    max_processes: int = MAX_DESCENDANT_PROCESSES,
) -> str | None:
    """Return a fresh daemon command below ``root_pid``, or ``None`` fail-closed.

    The root is deliberately excluded.  A tmux pane shell is commonly started
    with ``bash -c '<overseerd command>'``, so its own command line can mention
    ``overseerd`` even after the child has died.  Only a live descendant's
    ``/proc`` command line establishes daemon liveness.
    """
    pending = list(children_of(pid=root_pid))
    seen = {root_pid}
    while pending and len(seen) < max_processes:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        raw = cmdline_of(pid=pid)
        if raw is not None:
            command = raw.replace(b"\0", b" ").decode(errors="replace").strip()
            if daemon_liveness.is_daemon_command(text=command):
                return command
        pending.extend(children_of(pid=pid))
    return None
