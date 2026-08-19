"""Public Claude Code session discovery API."""

from __future__ import annotations

import os
from pathlib import Path

import _claude_sessions_proc
import _claude_sessions_registry
from _claude_sessions_registry import ClaudeSession, default_sessions_dir
from _claude_sessions_subshell import has_active_subshell
from _claude_sessions_tmux import (
    identities_by_tmux_session,
    map_named_sessions,
    names_by_tmux_session,
    resolve_tmux_session,
    status_by_tmux_session,
)
from _seams import PidToOptionalStr

__all__: list[str] = [
    "ClaudeSession",
    "default_sessions_dir",
    "has_active_subshell",
    "identities_by_tmux_session",
    "map_named_sessions",
    "names_by_tmux_session",
    "proc_children",
    "proc_cmdline",
    "proc_comm",
    "proc_environ",
    "proc_ppid",
    "proc_starttime",
    "read_live_sessions",
    "resolve_tmux_session",
    "status_by_tmux_session",
]


def _sync_reader_paths() -> None:
    _claude_sessions_proc.Path = Path
    _claude_sessions_registry.Path = Path


def proc_ppid(*, pid: int) -> int | None:
    _sync_reader_paths()
    return _claude_sessions_proc.proc_ppid(pid=pid)


def proc_starttime(*, pid: int) -> str | None:
    _sync_reader_paths()
    return _claude_sessions_proc.proc_starttime(pid=pid)


def proc_comm(*, pid: int) -> str | None:
    _sync_reader_paths()
    return _claude_sessions_proc.proc_comm(pid=pid)


def proc_cmdline(*, pid: int) -> bytes | None:
    _sync_reader_paths()
    return _claude_sessions_proc.proc_cmdline(pid=pid)


def proc_environ(*, pid: int) -> bytes | None:
    _sync_reader_paths()
    return _claude_sessions_proc.proc_environ(pid=pid)


def proc_children(*, pid: int) -> list[int]:
    _sync_reader_paths()
    return _claude_sessions_proc.proc_children(pid=pid)


def read_live_sessions(
    *,
    sessions_dir: str | os.PathLike[str],
    starttime_of: PidToOptionalStr = proc_starttime,
) -> list[ClaudeSession]:
    _sync_reader_paths()
    return _claude_sessions_registry.read_live_sessions(
        sessions_dir=sessions_dir, starttime_of=starttime_of
    )
