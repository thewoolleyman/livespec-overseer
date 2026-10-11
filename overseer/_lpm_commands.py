"""The one manager command dispatcher used by both installed launchers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ManagerInvocation",
    "ManagerRuntime",
    "run_manager_command",
]

_Outcome_co = TypeVar("_Outcome_co", covariant=True)


@dataclass(frozen=True, kw_only=True)
class ManagerInvocation:
    """One recognized object-carrying manager command."""

    command: str
    source: str | None


class ManagerRuntime(Protocol[_Outcome_co]):
    """The concrete host boundary reached after argv validation."""

    def run(self, *, invocation: ManagerInvocation) -> _Outcome_co:
        """Run one recognized invocation."""
        ...


def run_manager_command(
    *, arguments: Sequence[str], runtime: ManagerRuntime[_Outcome_co]
) -> _Outcome_co:
    """Delegate an already shape-validated object command to the shared runtime."""
    if not arguments or (len(arguments) == 1 and arguments[0] == "attention"):
        return runtime.run(invocation=ManagerInvocation(command="attention", source=None))
    return runtime.run(invocation=ManagerInvocation(command=arguments[0], source=arguments[2]))
