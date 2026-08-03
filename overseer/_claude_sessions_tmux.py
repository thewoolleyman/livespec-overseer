"""Join live Claude registry sessions to owning tmux sessions.

After registry parsing proves a Claude PID is live, the supervisor maps it to
the tmux session whose pane process-tree contains that PID. The join walks from
the Claude process up to a known tmux pane PID, producing screen-independent
``(tmux_session, name, cwd)`` data that still works while the pane is at a user
prompt or otherwise rendering no input box. The parent-chain and start-time
readers are injected, keeping this join deterministic under tests.
"""

from __future__ import annotations

import os

from _claude_sessions_proc import proc_ppid, proc_starttime
from _claude_sessions_registry import read_live_sessions
from _seams import PidToOptionalInt, PidToOptionalStr

__all__: list[str] = [
    "map_named_sessions",
    "names_by_tmux_session",
    "resolve_tmux_session",
    "status_by_tmux_session",
]

# A claude PID's parent chain is a handful deep (claude -> shell -> tmux pane);
# bound the walk so a cycle or a pathological tree can never spin.
_MAX_PARENT_WALK = 64


def resolve_tmux_session(
    *,
    pid: int,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
) -> str | None:
    """The tmux session whose pane process-tree contains ``pid``, or None.

    Walks ``pid`` UP its parent chain; the first ancestor (or ``pid`` itself) that
    is a tmux pane PID gives the owning session. A claude PID's parent is its
    pane's shell (a pane PID), so this resolves in one or two hops; the bounded
    walk plus a visited-set make a cycle or a very deep tree fail-soft to None.
    """
    current = pid
    seen: set[int] = set()
    for _ in range(_MAX_PARENT_WALK):
        session = pane_pid_to_session.get(current)
        if session is not None:
            return session
        if current in seen:
            return None
        seen.add(current)
        parent = ppid_of(pid=current)
        if parent is None or parent <= 0 or parent == current:
            return None
        current = parent
    return None


def map_named_sessions(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    starttime_of: PidToOptionalStr = proc_starttime,
) -> list[tuple[str, str, str]]:
    """``[(tmux_session, name, cwd)]`` for every live named session held in tmux.

    Composes :func:`read_live_sessions` with :func:`resolve_tmux_session`. A live
    session that is not inside any tmux pane (run outside tmux) is omitted. Order
    follows the sorted registry files, so the mapping is deterministic.
    """
    mapped: list[tuple[str, str, str]] = []
    for session in read_live_sessions(sessions_dir=sessions_dir, starttime_of=starttime_of):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is None:
            continue
        mapped.append((tmux_session, session.name, session.cwd))
    return mapped


def status_by_tmux_session(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    starttime_of: PidToOptionalStr = proc_starttime,
) -> dict[str, str]:
    """``{tmux_session: status}`` for every live named Claude session held in tmux.

    Claude Code writes a live ``status`` (``busy`` / ``idle`` / ``waiting``) into each
    session's registry file. This is an AUTHORITATIVE busy signal for an adopted Claude
    session — it is TRUE while the session runs an in-process sub-agent (Task tool), which
    :func:`has_active_subshell` cannot see (a sub-agent spawns no descendant shell) and a
    single pane capture can miss. The daemon folds ``status == "busy"`` into its busy
    check so a sub-agent-running session is never mis-read as idle.

    Same join as :func:`map_named_sessions` (registry ⋈ tmux by PID walk); keyed by the
    tmux session so the daemon can look up a track's session in O(1). When two live
    sessions resolve to the same tmux session (should not happen in practice) the last
    wins, matching the sorted-file iteration order.
    """
    out: dict[str, str] = {}
    for session in read_live_sessions(sessions_dir=sessions_dir, starttime_of=starttime_of):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is not None:
            out[tmux_session] = session.status
    return out


def names_by_tmux_session(
    *,
    sessions_dir: str | os.PathLike[str],
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    starttime_of: PidToOptionalStr = proc_starttime,
) -> dict[str, set[str]]:
    """``{tmux_session: {name, ...}}`` — the set of ALL live named Claude session names in
    each tmux session.

    Unlike :func:`status_by_tmux_session` (last-wins, one value per tmux session), this keeps
    EVERY name, so the daemon's identity gate can ask "is a live Claude named ``<topic>`` in
    this tmux session?" even when a HELPER Claude shares the tmux session (a second window/
    split). A last-wins single name would let that helper's name shadow the track's own and
    flap a healthy track to ``session-gone`` (R2 review SF5, 2026-07-18). Same registry ⋈
    tmux PID-walk join as :func:`status_by_tmux_session`.
    """
    out: dict[str, set[str]] = {}
    for session in read_live_sessions(sessions_dir=sessions_dir, starttime_of=starttime_of):
        tmux_session = resolve_tmux_session(
            pid=session.pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is not None:
            out.setdefault(tmux_session, set()).add(session.name)
    return out
