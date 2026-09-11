"""Live process sources for launch-profile reads."""

from __future__ import annotations

import os
from dataclasses import dataclass

import _codex_runtime_model
import claude_sessions
import codex_sessions
from _seams import (
    CodexStateModelReader,
    PidToOptionalBytes,
    PidToOptionalInt,
    PidToOptionalStr,
)

__all__: list[str] = [
    "CodexModelSource",
    "LaunchProfileSource",
    "codex_model_source",
    "live_profile_sources",
]


@dataclass(frozen=True, kw_only=True)
class LaunchProfileSource:
    pid: int
    harness: str
    pane_pid: int | None
    # The live session identity this source was discovered UNDER, carried rather than
    # re-derived. Only the Codex arm establishes one (pid → open-rollout filename →
    # index), so both stay None for Claude; a Codex source without one does not exist,
    # because discovery drops a carrier whose rollout set names no indexed session.
    session_id: str | None = None
    cwd: str | None = None


@dataclass(frozen=True, kw_only=True)
class CodexModelSource:
    """A Codex track's established live identity, bound to the state-database reader.

    Bundling the identity with its reader is what keeps the reader from CHOOSING one:
    everything it is allowed to ask about arrives here, already proven from process
    evidence by the discovery pass that produced the :class:`LaunchProfileSource`.
    """

    session_id: str
    cwd: str
    codex_home: str | os.PathLike[str] | None
    read: CodexStateModelReader


def codex_model_source(
    *,
    source: LaunchProfileSource,
    environ_of: PidToOptionalBytes,
    codex_home: str | os.PathLike[str] | None,
    read: CodexStateModelReader = _codex_runtime_model.read_runtime_model,
) -> CodexModelSource | None:
    """Bind the state-database reader to a source's ALREADY-ESTABLISHED live identity.

    ``None`` — the unusable case — whenever no single live session identity is tied to
    this source, which is every non-Codex harness and any Codex carrier discovery
    refused to name. The Codex home is the CARRIER's own ``CODEX_HOME`` when it sets a
    non-empty one, else the daemon-wide home seam.
    """
    if source.session_id is None or source.cwd is None:
        return None
    return CodexModelSource(
        session_id=source.session_id,
        cwd=source.cwd,
        codex_home=_codex_runtime_model.carrier_codex_home(
            pid=source.pid,
            environ_of=environ_of,
            fallback=codex_home,
        ),
        read=read,
    )


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
    readers: codex_sessions.CodexHostReaders,
) -> dict[tuple[str, str], LaunchProfileSource]:
    out: dict[tuple[str, str], LaunchProfileSource] = {}
    for session in codex_sessions.read_live_codex_sessions(
        codex_home=readers.codex_home,
        pids_of_comm=readers.pids_of_comm,
        cwd_of=readers.cwd_of,
        fd_targets_of=readers.fd_targets_of,
        children_of=readers.children_of,
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
                session_id=session.session_id,
                cwd=session.cwd,
            )
    return out


def live_profile_sources(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt,
    starttime_of: PidToOptionalStr,
    codex_readers: codex_sessions.CodexHostReaders,
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
