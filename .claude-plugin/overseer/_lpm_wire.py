"""Encode the manager's one-line result and decode its one JSON input."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import parse_canonical_json
from _lpm_results import ManagerError, error_object, exit_status_for

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CommandOutcome",
    "error_outcome",
    "read_command_object",
    "render_outcome",
    "success_outcome",
]


@dataclass(frozen=True, kw_only=True)
class CommandOutcome:
    """One exact JSON object and the process status that belongs to it."""

    body: dict[str, object]
    exit_status: int


def success_outcome(*, payload: dict[str, object]) -> CommandOutcome:
    """Wrap an operation payload in the common success envelope."""
    body: dict[str, object] = {"version": 1, "status": "ok"}
    body.update(payload)
    return CommandOutcome(body=body, exit_status=0)


def error_outcome(*, error: ManagerError) -> CommandOutcome:
    """Wrap one typed failure with its contract-defined process status."""
    return CommandOutcome(
        body=error_object(error=error),
        exit_status=exit_status_for(error_type=error.error_type),
    )


def render_outcome(*, outcome: CommandOutcome) -> str:
    """Render exactly one compact, UTF-8-safe JSON line without its newline."""
    return json.dumps(outcome.body, ensure_ascii=False, separators=(",", ":"))


def read_command_object(
    *, source: str, read_input: Callable[[], str], refuse: Callable[..., ManagerError]
) -> Result[object, ManagerError]:
    """Read <path|-> as exactly one duplicate-free JSON object."""
    if source == "-":
        text = read_input()
    else:
        try:
            text = Path(source).read_text(encoding="utf-8")
        except (OSError, ValueError):
            return Failure(refuse(message="the command input could not be read as UTF-8"))
    parsed = parse_canonical_json(text=text)
    if isinstance(parsed, Failure) or not isinstance(parsed.unwrap(), dict):
        return Failure(refuse(message="the command input is not exactly one JSON object"))
    return Success(parsed.unwrap())
