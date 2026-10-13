"""Fixed-command terminal execution with sanitizer-only incremental output."""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from _lpm_env import scrubbed_environment
from _lpm_observations import ObservationOutcome, ObservationSanitizer

__all__: list[str] = [
    "ExecutionCommand",
    "TerminalPerformer",
]


@dataclass(frozen=True, kw_only=True)
class ExecutionCommand:
    """One immutable canonical executable identity and its fixed arguments."""

    path: str
    device: int
    inode: int
    arguments: tuple[str, ...]


@dataclass(kw_only=True)
class _TerminalState:
    pid: int
    stdin_descriptor: int
    stdout_descriptor: int
    stderr_descriptor: int
    stdout: bytearray = field(default_factory=bytearray, repr=False)
    stderr: bytearray = field(default_factory=bytearray, repr=False)
    reaped: bool = False
    exit_status: int | None = None
    stdout_closed: bool = False
    stderr_closed: bool = False


@dataclass(kw_only=True)
class TerminalPerformer:
    """Own one fixed execution terminal and expose no unsanitized output surface."""

    command: ExecutionCommand
    sanitizer: ObservationSanitizer = field(repr=False)
    environ: Mapping[str, str] = field(repr=False)
    read_timeout_seconds: float
    _state: _TerminalState | None = field(default=None, init=False, repr=False)

    def start(self) -> dict[str, object]:
        """Start the immutable command at most once with credential overrides removed."""
        if self._state is not None or not _reference_is_current(command=self.command):
            return _unavailable()
        state = _spawn(command=self.command, environ=scrubbed_environment(environ=self.environ))
        if state is None:
            return _unavailable()
        self._state = state
        return _ok()

    def observe(self) -> ObservationOutcome:
        """Return only newly released text from the incremental terminal sanitizer."""
        state = self._state
        if state is None:
            return _unavailable_observation()
        _read_available(state=state, timeout_seconds=self.read_timeout_seconds)
        running, exit_status = _poll(state=state)
        try:
            stdout = state.stdout.decode("utf-8")
            stderr = state.stderr.decode("utf-8")
        except UnicodeDecodeError:
            return _unavailable_observation()
        return self.sanitizer.terminal_observation(
            running=running,
            exit_status=exit_status,
            stdout=stdout,
            stderr=stderr,
        )

    def send_line(self, *, text: str) -> dict[str, object]:
        """Write one already-validated non-secret line without exposing terminal output."""
        state = self._state
        if state is None:
            return _unavailable()
        payload = f"{text}\n".encode()
        sent = 0
        while sent < len(payload):
            sent += os.write(state.stdin_descriptor, payload[sent:])
        return _ok()

    def close(self) -> None:
        """Close service descriptors after the fixed command has been observed exiting."""
        state = cast("_TerminalState", self._state)
        _ = _poll(state=state)
        for descriptor in (
            state.stdin_descriptor,
            state.stdout_descriptor,
            state.stderr_descriptor,
        ):
            os.close(descriptor)
        self._state = None


def _reference_is_current(*, command: ExecutionCommand) -> bool:
    status = Path(command.path).stat(follow_symlinks=False)
    return (
        stat.S_ISREG(status.st_mode)
        and status.st_dev == command.device
        and status.st_ino == command.inode
        and os.access(command.path, os.X_OK)
    )


def _spawn(*, command: ExecutionCommand, environ: Mapping[str, str]) -> _TerminalState | None:
    child_stdin, service_stdin = os.pipe2(os.O_CLOEXEC)
    service_stdout, child_stdout = os.pipe2(os.O_CLOEXEC)
    service_stderr, child_stderr = os.pipe2(os.O_CLOEXEC)
    descriptors = (
        child_stdin,
        service_stdin,
        service_stdout,
        child_stdout,
        service_stderr,
        child_stderr,
    )
    actions = (
        (os.POSIX_SPAWN_DUP2, child_stdin, 0),
        (os.POSIX_SPAWN_DUP2, child_stdout, 1),
        (os.POSIX_SPAWN_DUP2, child_stderr, 2),
        *((os.POSIX_SPAWN_CLOSE, descriptor) for descriptor in descriptors),
    )
    try:
        pid = os.posix_spawn(
            command.path,
            (command.path, *command.arguments),
            dict(environ),
            file_actions=actions,
            setpgroup=0,
        )
    except OSError:
        _close_descriptors(descriptors=descriptors)
        return None
    _close_descriptors(descriptors=(child_stdin, child_stdout, child_stderr))
    os.set_blocking(service_stdout, False)
    os.set_blocking(service_stderr, False)
    return _TerminalState(
        pid=pid,
        stdin_descriptor=service_stdin,
        stdout_descriptor=service_stdout,
        stderr_descriptor=service_stderr,
    )


def _read_available(*, state: _TerminalState, timeout_seconds: float) -> None:
    targets = {
        state.stdout_descriptor: state.stdout,
        state.stderr_descriptor: state.stderr,
    }
    deadline = time.monotonic() + timeout_seconds
    while True:
        changed = False
        for descriptor, target in targets.items():
            prior_length = len(target)
            closed = _drain(descriptor=descriptor, target=target)
            if descriptor == state.stdout_descriptor:
                state.stdout_closed = closed
            else:
                state.stderr_closed = closed
            changed = changed or closed or len(target) != prior_length
        if changed or time.monotonic() >= deadline:
            return
        time.sleep(min(0.001, max(0.0, deadline - time.monotonic())))


def _drain(*, descriptor: int, target: bytearray) -> bool:
    while True:
        try:
            chunk = os.read(descriptor, 65536)
        except BlockingIOError:
            return False
        if not chunk:
            return True
        target.extend(chunk)


def _poll(*, state: _TerminalState) -> tuple[bool, int | None]:
    if not state.reaped:
        options = 0 if state.stdout_closed and state.stderr_closed else os.WNOHANG
        waited, status = os.waitpid(state.pid, options)
        if waited != 0:
            state.reaped = True
            state.exit_status = os.waitstatus_to_exitcode(status)
    return not state.reaped, state.exit_status


def _close_descriptors(*, descriptors: tuple[int, ...]) -> None:
    for descriptor in descriptors:
        os.close(descriptor)


def _ok() -> dict[str, object]:
    return {"version": 1, "status": "ok"}


def _unavailable() -> dict[str, object]:
    return {"version": 1, "status": "unavailable"}


def _unavailable_observation() -> ObservationOutcome:
    return ObservationOutcome(
        response=_unavailable(),
        fingerprint=None,
        stop_reason="flow-unavailable",
    )
