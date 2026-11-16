"""Local role-holder execution for the Remote Control reissue script."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

import caam_delivery_push_state

__all__: list[str] = ["run_reissue_script"]

Run = Callable[..., subprocess.CompletedProcess[str]]


def run_reissue_script(
    *,
    script: str,
    timeout: float,
    run: Run = subprocess.run,
    executable: str = sys.executable,
) -> str:
    """Run a local reissue script and return its secret-free result line."""
    try:
        done = run(
            [executable, "-"],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return f"failed {type(error).__name__}"
    lines = done.stdout.strip().splitlines()
    return (
        caam_delivery_push_state.scrubbed(text=lines[-1])
        if lines
        else f"failed exit {done.returncode}"
    )
