"""Shared flag protocol for the caam account-rotation pass."""

from __future__ import annotations

from typing import Protocol

__all__: list[str] = [
    "Flags",
]


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
    def foreman_model(self) -> str | None: ...

    @property
    def session_models(self) -> tuple[tuple[str, str], ...]: ...
