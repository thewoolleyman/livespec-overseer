"""Tmux helpers used by prompt-quality discrimination tests."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

__all__: list[str] = ["wait_for_pane_current_path"]

# This waits only for tmux to report the `new-session -c` cwd after shell
# startup, not for any pane command to finish. The peer measurement observed the
# startup transient inside a 1s sampling window under load; 2s doubles that
# measured window while keeping absent or wrong-pane failures prompt.
_PANE_CWD_TIMEOUT_S = 2.0
_PANE_CWD_POLL_INTERVAL_S = 0.05


def wait_for_pane_current_path(
    *,
    tmux: Callable[..., subprocess.CompletedProcess[str]],
    target: str,
    expected: Path,
    timeout_s: float = _PANE_CWD_TIMEOUT_S,
    poll_interval_s: float = _PANE_CWD_POLL_INTERVAL_S,
) -> str:
    """Poll `#{pane_current_path}` until it equals the expected cwd or times out."""
    deadline = time.monotonic() + timeout_s
    expected_text = str(expected)
    last = ""
    while True:
        last = tmux("display-message", "-p", "-t", target, "#{pane_current_path}").stdout.strip()
        if last == expected_text or time.monotonic() >= deadline:
            return last
        time.sleep(poll_interval_s)
