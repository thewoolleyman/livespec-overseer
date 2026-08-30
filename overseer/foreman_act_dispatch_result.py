"""Command-result adapters for authorized foreman dispatch actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

__all__: list[str] = [
    "CommandResult",
    "ReturncodeRunner",
    "Runner",
    "command_result",
]

STDERR_TAIL_BYTES: Final[int] = 2000


@dataclass(frozen=True, kw_only=True)
class CommandResult:
    returncode: int
    stderr: str = ""
    stdout: str = ""

    def diagnostics(self, *, argv: list[str]) -> dict[str, object]:
        """What a failing launch owes its journal beyond the exit status.

        `command_exit_1` names the status and nothing else, which left the
        measured 2026-08-30 failure with no argv to reproduce and no message to
        read. The stderr is a TAIL rather than the whole stream because the
        child is unbounded and the journal line is durable; the argv is copied
        so a later mutation of the caller's list cannot rewrite the record of
        what ran.
        """
        return {"argv": list(argv), "stderr": self.stderr[-STDERR_TAIL_BYTES:]}


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
