"""Codex 0.164 app-server helpers never become a TUI session's carrier."""

from __future__ import annotations

import _codex_proc
import codex_sessions
from test_codex_sessions_fakes import ID_A, fake_host, fake_index, fake_rollout


def test_a_detached_app_server_rollout_belongs_to_its_terminal_tui(*, tmp_path, monkeypatch):
    """The 0.164 app-server tree: TUI -> daemon -> detached rollout helper.

    The app-server processes have Codex's ``comm`` and the repository cwd, and the
    last one holds the only rollout. Their separate process sessions leave them
    without the pane terminal's foreground group; the TUI has that group and must
    remain the reported session carrier.
    """
    tui_pid = 137
    app_server_daemon_pid = 379
    app_server_helper_pid = 2745
    home = fake_index(tmp_path=tmp_path, records=[(ID_A, "overseer-proof")])
    host = fake_host(
        comms={
            tui_pid: "codex",
            app_server_daemon_pid: "codex",
            app_server_helper_pid: "codex",
        },
        cwds={
            tui_pid: "/data/projects/livespec-overseer",
            app_server_daemon_pid: "/data/projects/livespec-overseer",
            app_server_helper_pid: "/data/projects/livespec-overseer",
        },
        fds={app_server_helper_pid: [fake_rollout(session_id=ID_A)]},
        children={
            tui_pid: [app_server_daemon_pid],
            app_server_daemon_pid: [app_server_helper_pid],
        },
    )
    monkeypatch.setattr(
        _codex_proc,
        "proc_foreground_pgrp",
        lambda *, pid: 113 if pid == tui_pid else None,
        raising=False,
    )

    sessions = codex_sessions.read_live_codex_sessions(codex_home=home, **host)

    assert sessions == [
        codex_sessions.CodexSession(
            pid=tui_pid,
            name="overseer-proof",
            cwd="/data/projects/livespec-overseer",
            session_id=ID_A,
        )
    ]
