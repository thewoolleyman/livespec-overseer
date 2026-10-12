"""Render one retained-shell Herdr launch with an exact environment delta."""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping

__all__: list[str] = ["render_launch"]

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INVALID_ENV = "launch environment contains an invalid variable name"


def render_launch(*, cwd: str, command: str, env: Mapping[str, str | None]) -> str:
    """Apply cwd, explicit removals, and assignments before the recorded command."""
    if any(_ENV_NAME.fullmatch(name) is None for name in env):
        raise ValueError(_INVALID_ENV)
    removals = [
        part for name, value in sorted(env.items()) if value is None for part in ("-u", name)
    ]
    assignments = [f"{name}={value}" for name, value in sorted(env.items()) if value is not None]
    # `exec` makes the agent REPLACE the wrapper shell, so the pane's foreground group
    # leader is the agent itself; a lingering `sh` parent hid the successor from the
    # daemon's managed-agent check, and the continuation was never sent.
    launched = f"exec {command}"
    environment = shlex.join(["env", *removals, *assignments, "sh", "-c", launched])
    return f"cd -- {shlex.quote(cwd)} && {environment}"
