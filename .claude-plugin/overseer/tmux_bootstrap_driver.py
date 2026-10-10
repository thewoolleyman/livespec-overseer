"""Construct a tmux bootstrap driver retained to one selected socket."""

from __future__ import annotations

import terminal_probes
import tmux_process
import tmuxio

__all__: list[str] = ["socket_scoped_driver"]


def socket_scoped_driver(
    *, socket_path: str, run: tmux_process.TextProcessRun = tmux_process.TEXT_PROCESS_RUN
) -> tmuxio.TmuxIO:
    """Keep legacy argv for the default server and bind named servers with `-S`."""
    if socket_path == terminal_probes.DEFAULT_TMUX_ENDPOINT:
        return tmuxio.TmuxIO(run=run)
    return tmuxio.TmuxIO(run=tmux_process.SocketScopedRun(socket_path=socket_path, run=run))
