"""Construct a tmux bootstrap driver retained to one selected socket."""

from __future__ import annotations

import terminal_probes
import tmux_process
import tmuxio
import tmuxio_protocols

__all__: list[str] = ["bind_server_generation", "socket_scoped_driver"]


def bind_server_generation(
    *,
    driver: tmuxio_protocols.BootstrapDriver,
    server_pid: int,
    server_starttime: str,
    split_height_percent: int,
) -> tmuxio_protocols.BootstrapDriver:
    """Bind the real bootstrap driver; injected deterministic drivers stay unchanged."""
    if not isinstance(driver, tmuxio.TmuxIO):
        return driver
    return tmuxio.TmuxIO(
        tmux_bin=driver.tmux_binary(),
        run=tmux_process.GenerationBoundRun(
            server_pid=server_pid,
            server_starttime=server_starttime,
            split_height_percent=split_height_percent,
            run=driver.text_process_run(),
        ),
    )


def socket_scoped_driver(
    *, socket_path: str, run: tmux_process.TextProcessRun = tmux_process.TEXT_PROCESS_RUN
) -> tmuxio.TmuxIO:
    """Keep legacy argv for the default server and bind named servers with `-S`."""
    if socket_path == terminal_probes.DEFAULT_TMUX_ENDPOINT:
        return tmuxio.TmuxIO(run=run)
    return tmuxio.TmuxIO(run=tmux_process.SocketScopedRun(socket_path=socket_path, run=run))
