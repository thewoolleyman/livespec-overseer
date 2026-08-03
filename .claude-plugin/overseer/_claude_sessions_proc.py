"""Host ``/proc`` readers for Claude and Codex session discovery.

This is the process-table coupling for the session registry and tmux joins:
parent PID, process start-time, command name, and direct children. Callers accept
these readers as injectable callables so the beside-tests drive PID identity,
PID-reuse, and descendant-shell cases with fakes instead of touching the host's
real ``/proc`` tree or ``~/.claude`` registry.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

__all__: list[str] = [
    "proc_children",
    "proc_comm",
    "proc_ppid",
    "proc_starttime",
]

# --------------------------------------------------------------------------- #
# The ONE host coupling: /proc readers. Injected into the pure join below.
# --------------------------------------------------------------------------- #


def _proc_stat_fields(*, pid: int) -> list[str] | None:
    """``/proc/<pid>/stat`` split AFTER the ``(comm)`` field, or None if unreadable.

    ``comm`` (field 2) can contain spaces and parentheses, so everything up to and
    including the LAST ``)`` is dropped; the returned list is field 3 onward, i.e.
    ``fields[i]`` is stat field ``i + 3`` (state=fields[0], ppid=fields[1],
    starttime=fields[19]).
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    cut = raw.rfind(")")
    if cut == -1:
        return None
    return raw[cut + 1 :].split()


# Indices into the post-``)`` remainder of ``/proc/<pid>/stat`` that
# :func:`_proc_stat_fields` returns. The kernel numbers stat's fields from 1 and
# that remainder begins at field 3, so the field numbered F sits at index F - 3.
_PPID_INDEX = 1  # stat field 4
_STARTTIME_INDEX = 19  # stat field 22


def proc_ppid(*, pid: int) -> int | None:
    """The parent PID of ``pid`` from ``/proc/<pid>/stat`` (field 4), or None."""
    fields = _proc_stat_fields(pid=pid)
    if fields is None or len(fields) <= _PPID_INDEX:
        return None
    try:
        return int(fields[_PPID_INDEX])
    except ValueError:
        return None


def proc_starttime(*, pid: int) -> str | None:
    """The process start-time of ``pid`` from ``/proc/<pid>/stat`` (field 22), or None.

    Returned as a string to compare byte-for-byte against the registry's
    ``procStart`` (also a string). None if the process is gone / unreadable — which
    the caller treats as "not live".
    """
    fields = _proc_stat_fields(pid=pid)
    if fields is None or len(fields) <= _STARTTIME_INDEX:
        return None
    return fields[_STARTTIME_INDEX]


# Shell process names. Most are task shells, but some agent runtimes also create
# short startup wrapper shells before launching long-lived MCP helpers; start-time
# evidence below separates those startup shells from later background work.
_SHELL_COMMS = frozenset({"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"})


def proc_comm(*, pid: int) -> str | None:
    """``/proc/<pid>/comm`` (the process's command name), or None if unreadable."""
    try:
        return (
            Path(f"/proc/{pid}/comm").read_text(encoding="utf-8", errors="replace").strip() or None
        )
    except OSError:
        return None


def proc_children(*, pid: int) -> list[int]:
    """Direct child PIDs of ``pid`` via ``/proc/<pid>/task/<pid>/children`` ([] on error)."""
    try:
        data = Path(f"/proc/{pid}/task/{pid}/children").read_text(encoding="utf-8")
    # ValueError is defence-in-depth here, not a live hazard: the kernel writes this
    # file as ASCII pids and spaces, so it cannot fail to decode. Widened anyway so
    # every read boundary in the package carries ONE rule rather than two.
    except (OSError, ValueError):
        return []
    out: list[int] = []
    for token in data.split():
        with contextlib.suppress(ValueError):
            out.append(int(token))
    return out
