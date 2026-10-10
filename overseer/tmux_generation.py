"""Exact selected-generation interlock for retained tmux bootstrap actions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar

import terminal_ownership
import tmuxio_protocols

__all__: list[str] = ["guard"]

_Result = TypeVar("_Result")
_Result_co = TypeVar("_Result_co", covariant=True)


class _Invalid(Protocol[_Result_co]):
    def __call__(self, *, error: str) -> _Result_co: ...


def _error(
    *,
    driver: tmuxio_protocols.BootstrapDriver,
    claim: terminal_ownership.OwnershipClaim,
    daemon_executable: Path | None,
) -> str:
    """Why the retained driver no longer answers for the selected generation."""
    if daemon_executable is None:
        return ""
    actual = driver.server_generation()
    expected = (claim.server_pid, claim.server_starttime)
    if actual != expected:
        return f"the selected tmux server generation changed from {expected!r} to {actual!r}"
    return ""


def guard(
    *,
    driver: tmuxio_protocols.BootstrapDriver,
    claim: terminal_ownership.OwnershipClaim,
    daemon_executable: Path | None,
    valid: Callable[[], _Result],
    invalid: _Invalid[_Result],
) -> _Result:
    """Run `valid` only while the driver still names the selected generation."""
    error = _error(driver=driver, claim=claim, daemon_executable=daemon_executable)
    if error:
        return invalid(error=error)
    return valid()
