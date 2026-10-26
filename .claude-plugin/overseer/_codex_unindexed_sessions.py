"""The tmux join for live Codex carriers absent from the session index.

Named Codex discovery belongs to :mod:`codex_sessions`; this diagnostic path asks the
same carrier-and-rollout question but reports sessions whose rollout has no indexed
thread name. Keeping the path separate preserves the facade's focused named-session
join while making the unindexed diagnostic independently readable.
"""

from __future__ import annotations

from pathlib import Path

import codex_sessions
from _seams import PidToOptionalInt
from claude_sessions import proc_ppid, resolve_tmux_session

__all__: list[str] = ["map_unindexed_codex_sessions"]


def map_unindexed_codex_sessions(
    *,
    pane_pid_to_session: dict[int, str],
    ppid_of: PidToOptionalInt = proc_ppid,
    readers: codex_sessions.CodexHostReaders | None = None,
) -> list[codex_sessions.UnindexedCodexSession]:
    """Live Codex sessions that have a rollout fd but no ``session_index`` name.

    These cannot be adopted because the plan topic exists only as ``thread_name`` in
    the index. Returning them separately lets the supervisor make the gap visible
    without weakening the exact pid→rollout→name join and without reading rollout
    transcript contents.

    "Has a rollout" is asked through :func:`codex_sessions.carrier_rollout_ids`,
    exactly as the named join asks it, so the two answers cannot disagree: a session
    whose rollout is held by its helper is UNNAMED here only when that rollout is
    genuinely absent from the index, never merely because ownership moved off the
    carrier's own fd table. Asking the narrower question here would let one live
    session be reported as both named and unindexed at once.
    """
    host = readers if readers is not None else codex_sessions.CodexHostReaders()
    home = (
        Path(host.codex_home)
        if host.codex_home is not None
        else codex_sessions.default_codex_home()
    )
    names = codex_sessions.read_thread_names(codex_home=home)
    carriers = codex_sessions.codex_carriers(
        codex_home=home,
        pids_of_comm=host.pids_of_comm,
        environ_of=host.environ_of,
        foreground_pgrp_of=host.foreground_pgrp_of,
    )
    carrier_pids = frozenset(carriers.all_pids)
    unindexed: list[codex_sessions.UnindexedCodexSession] = []
    for pid in carriers.scoped:
        rollout_ids = codex_sessions.carrier_rollout_ids(
            pid=pid,
            carrier_pids=carrier_pids,
            fd_targets_of=host.fd_targets_of,
            children_of=host.children_of,
        )
        if not rollout_ids or any(names.get(session_id) for session_id in rollout_ids):
            continue
        session_id = rollout_ids[0]
        cwd = host.cwd_of(pid=pid)
        if not cwd:
            continue
        tmux_session = resolve_tmux_session(
            pid=pid, pane_pid_to_session=pane_pid_to_session, ppid_of=ppid_of
        )
        if tmux_session is None:
            continue
        unindexed.append(
            codex_sessions.UnindexedCodexSession(
                pid=pid,
                cwd=cwd,
                session_id=session_id,
                tmux_session=tmux_session,
            )
        )
    return unindexed
