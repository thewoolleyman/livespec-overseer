"""Live process sources for launch-profile reads."""

from __future__ import annotations

import os
from dataclasses import dataclass

import claude_sessions
import codex_sessions
from _seams import CommToPidList, PidToOptionalInt, PidToOptionalStr, PidToStrList

__all__: list[str] = [
    "CodexProfileReaders",
    "LaunchProfileSource",
    "live_profile_sources",
]


@dataclass(frozen=True, kw_only=True)
class CodexProfileReaders:
    codex_home: str | os.PathLike[str] | None
    pids_of_comm: CommToPidList
    cwd_of: PidToOptionalStr
    fd_targets_of: PidToStrList


@dataclass(frozen=True, kw_only=True)
class LaunchProfileSource:
    pid: int
    harness: str
    pane_pid: int | None


def _pane_pid_for_session(
    *,
    pane_pid_to_session: dict[int, str],
    tmux_session: str,
) -> int | None:
    return next((pid for pid, tmux in pane_pid_to_session.items() if tmux == tmux_session), None)


def _claude_sources(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt,
    starttime_of: PidToOptionalStr,
) -> dict[tuple[str, str], LaunchProfileSource]:
    out: dict[tuple[str, str], LaunchProfileSource] = {}
    for session in claude_sessions.read_live_sessions(
        sessions_dir=sessions_dir, starttime_of=starttime_of
    ):
        tmux_session = claude_sessions.resolve_tmux_session(
            pid=session.pid,
            pane_pid_to_session=pane_pid_to_session,
            ppid_of=ppid_of,
        )
        if tmux_session is not None:
            out[(tmux_session, session.name)] = LaunchProfileSource(
                pid=session.pid,
                harness="claude",
                pane_pid=_pane_pid_for_session(
                    pane_pid_to_session=pane_pid_to_session,
                    tmux_session=tmux_session,
                ),
            )
    return out


def _codex_sources(
    *,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt,
    readers: CodexProfileReaders,
) -> dict[tuple[str, str], LaunchProfileSource]:
    out: dict[tuple[str, str], LaunchProfileSource] = {}
    for session in codex_sessions.read_live_codex_sessions(
        codex_home=readers.codex_home,
        pids_of_comm=readers.pids_of_comm,
        cwd_of=readers.cwd_of,
        fd_targets_of=readers.fd_targets_of,
    ):
        tmux_session = claude_sessions.resolve_tmux_session(
            pid=session.pid,
            pane_pid_to_session=pane_pid_to_session,
            ppid_of=ppid_of,
        )
        if tmux_session is not None:
            out[(tmux_session, session.name)] = LaunchProfileSource(
                pid=session.pid,
                harness="codex",
                pane_pid=_pane_pid_for_session(
                    pane_pid_to_session=pane_pid_to_session,
                    tmux_session=tmux_session,
                ),
            )
    return out


def live_profile_sources(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt,
    starttime_of: PidToOptionalStr,
    codex_readers: CodexProfileReaders,
) -> dict[tuple[str, str], LaunchProfileSource]:
    """Return live launch-profile process sources keyed by ``(tmux_session, topic)``."""
    return _claude_sources(
        sessions_dir=sessions_dir,
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=ppid_of,
        starttime_of=starttime_of,
    ) | _codex_sources(
        pane_pid_to_session=pane_pid_to_session,
        ppid_of=ppid_of,
        readers=codex_readers,
    )
