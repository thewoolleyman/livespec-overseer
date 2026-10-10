"""Exact daemon-occupant reading for one generation-bound tmux pane."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import bootstrap
import daemon_liveness
import terminal_ownership
import tmuxio_protocols

__all__: list[str] = ["read_daemon_host"]


class _DaemonProcessReader(Protocol):
    def __call__(
        self, *, root_pid: int, daemon_executable: Path | None = None
    ) -> object | None: ...


def read_daemon_host(
    *,
    driver: tmuxio_protocols.BootstrapDriver,
    claim: terminal_ownership.OwnershipClaim,
    candidate: str,
    daemon_executable: Path | None,
    daemon_process_of: _DaemonProcessReader,
) -> bootstrap.DaemonHostReading:
    """Read a candidate through an already generation-validated driver."""
    command = driver.pane_current_command(session=candidate)
    if command is None:
        return bootstrap.DaemonHostReading(
            pane_id="",
            unresolved="",
            error=(
                f"the pane above {claim.pane_id!r} ({candidate!r}) has no readable "
                "foreground command"
            ),
        )
    pane_pid = driver.pane_pid(session=candidate)
    if pane_pid is None:
        daemon_process = None
    elif daemon_executable is None:
        daemon_process = daemon_process_of(root_pid=pane_pid)
    else:
        daemon_process = daemon_process_of(
            root_pid=pane_pid,
            daemon_executable=daemon_executable,
        )
    if daemon_process is not None:
        return bootstrap.DaemonHostReading(pane_id=candidate, unresolved="", error="")
    if daemon_liveness.is_retained_shell(name=command):
        return bootstrap.DaemonHostReading(
            pane_id="",
            unresolved=(
                f"pane {candidate!r} above {claim.pane_id!r} holds its retained shell "
                f"({command!r}) rather than a live daemon; a pane that outlived its "
                "daemon is not daemon liveness, so further action needs fresh "
                "exact-instance, pane and process evidence"
            ),
            error="",
        )
    return bootstrap.DaemonHostReading(
        pane_id="",
        unresolved=(
            f"pane {candidate!r} above {claim.pane_id!r} runs {command!r}, not the "
            "overseer daemon with a verified exact foreground identity; further "
            "action needs fresh exact-instance, pane and process evidence"
        ),
        error="",
    )
