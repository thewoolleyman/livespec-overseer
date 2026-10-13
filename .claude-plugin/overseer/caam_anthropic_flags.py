"""Shared flag protocol for the caam account-rotation pass."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__: list[str] = [
    "Flags",
    "scheduled_pass",
]


@runtime_checkable
class _ScheduledFlags(Protocol):
    @property
    def scheduled(self) -> bool: ...


def scheduled_pass(*, flags: object) -> bool:
    """Whether a flag carrier includes and enables the scheduler marker.

    Direct pass callers predate that marker, so absence is the explicitly
    unscheduled form rather than an attribute error halfway through a pass.
    """
    return isinstance(flags, _ScheduledFlags) and flags.scheduled


class Flags(Protocol):
    @property
    def force(self) -> bool: ...

    @property
    def dry_run(self) -> bool: ...

    @property
    def no_models(self) -> bool: ...

    @property
    def no_warm(self) -> bool: ...

    @property
    def session_models(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def protected_accounts(self) -> tuple[tuple[str, str], ...]: ...
