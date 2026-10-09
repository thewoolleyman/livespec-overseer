"""Build the shell command used to launch overseerd in a terminal pane."""

from __future__ import annotations

import shlex
from pathlib import Path

__all__: list[str] = ["build_daemon_command"]


def build_daemon_command(
    *, warn_percent: int | None, log_path: Path, daemon_executable: Path | None
) -> str:
    """Return the quoted daemon command with its bounded-history redirect."""
    base = shlex.quote(str(daemon_executable)) if daemon_executable is not None else "overseerd"
    if warn_percent is not None:
        base += f" --warn-percent {warn_percent}"
    return base + f" 2>> {shlex.quote(str(log_path))}"
