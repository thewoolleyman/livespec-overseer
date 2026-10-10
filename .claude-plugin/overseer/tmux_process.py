"""Typed text-process and named-socket seams shared by tmux callers."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast

__all__: list[str] = [
    "TEXT_PROCESS_RUN",
    "SocketScopedRun",
    "TextProcess",
    "TextProcessRun",
    "TmuxCall",
    "pane_field",
]

_PANE_ROW_FIELDS = 3


class TextProcess(Protocol):
    """The text-mode subprocess result consumed at the tmux boundary."""

    returncode: int
    stdout: str | None
    stderr: str | None


class TextProcessRun(Protocol):
    """One bounded text subprocess call."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> TextProcess: ...


class TmuxCall(Protocol):
    """One fail-soft tmux subcommand through an already selected runner."""

    def __call__(self, *, args: list[str], input_text: str | None = None) -> TextProcess | None: ...


# The stdlib overloads cannot express the one text-mode subset every caller uses.
TEXT_PROCESS_RUN = cast(TextProcessRun, subprocess.run)


@dataclass(frozen=True, kw_only=True)
class SocketScopedRun:
    """Insert one positively selected named socket into every tmux command."""

    socket_path: str
    run: TextProcessRun = TEXT_PROCESS_RUN

    def __call__(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> TextProcess:
        binary, *rest = argv
        return self.run(
            [binary, "-S", self.socket_path, *rest],
            input=input,
            capture_output=capture_output,
            text=text,
            check=check,
            timeout=timeout,
        )


def pane_field(*, call: TmuxCall, target: str, fmt: str) -> str | None:
    """Read one exact pane field from a complete `list-panes` answer."""
    completed = call(args=["list-panes", "-t", target, "-F", "#{pane_id}\t#{pane_active}\t" + fmt])
    if completed is None or completed.returncode != 0:
        return None
    rows = [
        parts
        for line in (completed.stdout or "").splitlines()
        if line.strip()
        for parts in [line.split("\t", _PANE_ROW_FIELDS - 1)]
        if len(parts) == _PANE_ROW_FIELDS
    ]
    if not rows:
        return None
    chosen = (
        next((row for row in rows if row[0] == target), None)
        if target.startswith("%")
        else next((row for row in rows if row[1] == "1"), rows[0])
    )
    if chosen is None:
        return None
    return chosen[2].strip() or None
