"""Diagnostic rows for live Codex sessions that cannot be adopted."""

from __future__ import annotations

from typing import TYPE_CHECKING

import codex_sessions
import signals
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["unindexed_codex_rows"]


def unindexed_codex_rows(*, sup: Supervisor, watch: list[str]) -> list[RowView]:
    """Attention rows for live Codex sessions that cannot be adopted.

    A Codex process with an open rollout but no ``session_index`` entry has live
    process evidence, a tmux coordinate, and a repo cwd, but no plan topic. The daemon
    must not guess the topic; it surfaces a synthetic row instead so the operator sees
    why a watched repo can still show an apparently ``unassigned`` plan.
    """
    rows: list[RowView] = []
    for session in codex_sessions.map_unindexed_codex_sessions(
        pane_pid_to_session=sup.tmux.pane_pid_sessions(),
        codex_home=sup.codex_home,
        ppid_of=sup.ppid_of,
        pids_of_comm=sup.codex_pids_of_comm,
        cwd_of=sup.codex_cwd_of,
        fd_targets_of=sup.codex_fd_targets_of,
    ):
        repo = next(
            (r for r in watch if signals.path_in_repo(pane_current_path=session.cwd, repo=r)), None
        )
        if repo is None:
            continue
        rows.append(
            RowView(
                topic=f"codex:{session.session_id[:8]}",
                repo=repo,
                tmux=session.tmux_session,
                ctx=None,
                status="codex-unindexed",
                note=(
                    f"live Codex rollout {session.session_id} has no "
                    "session_index thread_name; adoption cannot map it to a plan topic"
                ),
                runtime="codex",
            )
        )
    return rows
