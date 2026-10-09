"""Legacy injected-tmux orchestration retained beside verified public startup.

The shipped ``overseer-start`` path now selects a positively owned tmux or Herdr
instance.  Its long-standing injected ``WindowLayoutDriver`` seam remains useful
for deterministic tests and external callers, however, and this module keeps that
single concern together: recognize or create the titled top daemon pane, normalize
its height, then adopt already tracked sessions.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import daemon_log
import start_daemon_command
import streams
import supervisor
import tmuxio

__all__: list[str] = [
    "DAEMON_PANE_HEIGHT_PERCENT",
    "DAEMON_PANE_TITLE",
    "run_legacy_start",
]

DAEMON_PANE_TITLE = "overseer-daemon"
DAEMON_PANE_HEIGHT_PERCENT = 66
_OVERSEER_PANE_COUNT = 2


def _daemon_pane_is_top_of_two(*, layout: tmuxio.WindowLayoutDriver, pane: str) -> bool:
    geometries = layout.window_pane_geometries(pane=pane)
    if len(geometries) != _OVERSEER_PANE_COUNT:
        return False
    return any(geometry.pane == pane and geometry.top == 0 for geometry in geometries)


def _start_daemon_pane(
    *,
    layout: tmuxio.WindowLayoutDriver,
    pane: str,
    core: Path,
    warn_percent: int | None,
    daemon_executable: Path,
) -> bool:
    log_path = core / "tmp" / "overseer" / daemon_log.HISTORY_FILENAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = start_daemon_command.build_daemon_command(
        warn_percent=warn_percent,
        log_path=log_path,
        daemon_executable=daemon_executable,
    )
    new_pane = layout.split_window_top(pane=pane, cwd=str(core), command=command)
    if new_pane is None:
        streams.write_stderr(
            text="overseer-start: FAILED to split the window for the daemon pane.\n"
        )
        return False
    _ = layout.set_pane_title(pane=new_pane, title=DAEMON_PANE_TITLE)
    if not layout.pane_exists(pane=new_pane):
        streams.write_stderr(
            text=(
                "overseer-start: overseerd did not stay alive in the daemon pane; "
                f"check {log_path} for startup errors.\n"
            )
        )
        return False
    streams.write_stderr(text=f"overseer-start: started overseerd in top pane {new_pane}.\n")
    return True


def run_legacy_start(
    *,
    pane: str,
    warn_percent: int | None,
    layout: tmuxio.WindowLayoutDriver,
    build_supervisor: Callable[[], supervisor.Supervisor] | None,
    core: Path,
    ensure_daemon_runtime: Callable[[], Path | None],
) -> int:
    """Run the deterministic injected-driver tmux compatibility surface."""
    existing_daemon_pane = layout.pane_by_title(pane=pane, title=DAEMON_PANE_TITLE)
    if existing_daemon_pane is not None and _daemon_pane_is_top_of_two(
        layout=layout, pane=existing_daemon_pane
    ):
        streams.write_stderr(
            text="overseer-start: daemon pane already present in this window; leaving it.\n"
        )
    else:
        daemon_executable = ensure_daemon_runtime()
        if daemon_executable is None:
            streams.write_stderr(
                text=(
                    "overseer-start: failed to prepare the daemon-owned runtime prefix; "
                    "overseerd was not launched from the working tree.\n"
                )
            )
            return 1
        if not _start_daemon_pane(
            layout=layout,
            pane=pane,
            core=core,
            warn_percent=warn_percent,
            daemon_executable=daemon_executable,
        ):
            return 1
    _ = layout.select_layout_even(pane=pane)
    daemon_pane = layout.pane_by_title(pane=pane, title=DAEMON_PANE_TITLE)
    if daemon_pane is not None and _daemon_pane_is_top_of_two(layout=layout, pane=daemon_pane):
        _ = layout.set_pane_height_percent(pane=daemon_pane, percent=DAEMON_PANE_HEIGHT_PERCENT)
    build = build_supervisor if build_supervisor is not None else supervisor.build_supervisor
    adopted = build().adopt_sessions()
    for track in adopted:
        streams.write_stderr(
            text=f"overseer-start: adopted {track.tmux} → {track.repo}::{track.topic}\n"
        )
    streams.write_stderr(text=f"overseer-start: adopted {len(adopted)} existing session(s).\n")
    return 0
