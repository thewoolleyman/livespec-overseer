"""Environment delta assembly for tmux respawn commands."""

from __future__ import annotations

import shlex
from collections.abc import Mapping

__all__: list[str] = ["with_env_delta"]


def with_env_delta(*, command: str, env: Mapping[str, str | None] | None) -> str:
    if not env:
        return command
    parts = ["env"]
    for name, value in env.items():
        if value is None:
            parts.extend(["-u", name])
    for name, value in env.items():
        if value is not None:
            parts.append(f"{name}={value}")
    return " ".join(shlex.quote(part) for part in parts) + f" {command}"
