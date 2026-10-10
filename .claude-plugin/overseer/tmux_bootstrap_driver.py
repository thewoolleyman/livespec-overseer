"""Construct a tmux bootstrap driver retained to one selected socket."""

from __future__ import annotations

import terminal_probes
import tmux_process
import tmuxio
import tmuxio_protocols

__all__: list[str] = ["bind_server_generation", "socket_scoped_driver", "window_pane_rectangles"]


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


def window_pane_rectangles(
    *, driver: tmuxio_protocols.BootstrapDriver, pane: str
) -> list[tmuxio_protocols.PaneGeometry]:
    """Read full native rectangles while retaining older injected driver seams."""
    geometries = (
        driver.window_pane_rectangles(pane=pane)
        if isinstance(driver, tmuxio.TmuxIO)
        else driver.window_pane_geometries(pane=pane)
    )
    return [
        tmuxio_protocols.PaneGeometry(
            pane=geometry.pane,
            left=getattr(geometry, "left", 0),
            top=geometry.top,
            width=getattr(geometry, "width", 1),
            height=geometry.height,
        )
        for geometry in geometries
    ]
