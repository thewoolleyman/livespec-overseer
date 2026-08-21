"""Command-result adapters for authorized foreman dispatch actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

__all__: list[str] = [
    "CommandResult",
    "ReturncodeRunner",
    "Runner",
    "command_result",
]


@dataclass(frozen=True, kw_only=True)
class CommandResult:
    returncode: int
    stderr: str = ""


class Runner(Protocol):
    def __call__(self, *, argv: list[str]) -> int | CommandResult: ...


def command_result(*, raw: int | CommandResult) -> CommandResult:
    if isinstance(raw, int):
        return CommandResult(returncode=raw)
    return raw


def command_returncode(*, raw: int | CommandResult) -> int:
    return command_result(raw=raw).returncode


@dataclass(frozen=True, kw_only=True)
class ReturncodeRunner:
    run: Runner

    def __call__(self, *, argv: list[str]) -> int:
        return command_returncode(raw=self.run(argv=argv))
