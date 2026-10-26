"""Dependency contracts used by the pure caam switch coordinator."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from caam_decision import UsageRecord

__all__: list[str] = [
    "ActivateRunner",
    "ActiveReader",
    "CaamProcess",
    "SaveState",
    "UsageFetcher",
]


class CaamProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class ActivateRunner(Protocol):
    def __call__(self, *, args: tuple[str, ...], timeout: float) -> CaamProcess: ...


class ActiveReader(Protocol):
    def __call__(self) -> str | None: ...


class SaveState(Protocol):
    def __call__(self, *, state: dict[str, object]) -> None: ...


class UsageFetcher(Protocol):
    def __call__(
        self,
        *,
        creds_path: Path,
        now: float | None = None,
    ) -> tuple[UsageRecord | None, str | None]: ...
