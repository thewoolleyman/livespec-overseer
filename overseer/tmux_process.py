"""Typed text-process and named-socket seams shared by tmux callers."""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast

__all__: list[str] = [
    "TEXT_PROCESS_RUN",
    "GenerationBoundRun",
    "SocketScopedRun",
    "TextProcess",
    "TextProcessRun",
    "TmuxCall",
    "bootstrap_split_size",
    "pane_field",
]

_PANE_ROW_FIELDS = 3


def _generation_guard(*, server_pid: int, server_starttime: str) -> str:
    """A server-side shell predicate for the generation on this tmux connection."""
    return (
        f'[ "#{{pid}}" = "{server_pid}" ] && '
        f"IFS= read -r stat < /proc/{server_pid}/stat && "
        "stat=${stat##*) } && set -- $stat && "
        f'[ "${{20}}" = "{server_starttime}" ]'
    )


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


@dataclass(frozen=True, kw_only=True)
class GenerationBoundRun:
    """Run one command only on the selected generation of the connected server.

    ``if-shell`` evaluates the PID/start-time predicate and queues the real command
    on the SAME tmux client connection.  If that server exits after the predicate,
    the connection dies with it; the queued command cannot reconnect to a namesake
    that rebound the socket path.
    """

    server_pid: int
    server_starttime: str
    split_height_percent: int
    run: TextProcessRun

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
        binary, *command = argv
        guarded_argv = [
            binary,
            "if-shell",
            _generation_guard(
                server_pid=self.server_pid,
                server_starttime=self.server_starttime,
            ),
            shlex.join(command),
            shlex.join(["run-shell", "exit 125"]),
        ]
        return self.run(
            guarded_argv,
            input=input,
            capture_output=capture_output,
            text=text,
            check=check,
            timeout=timeout,
        )


def bootstrap_split_size(*, run: TextProcessRun) -> list[str]:
    """The allocation-scoped size carried only by a generation-bound bootstrap."""
    if not isinstance(run, GenerationBoundRun):
        return []
    return ["-l", f"{run.split_height_percent}%"]


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
