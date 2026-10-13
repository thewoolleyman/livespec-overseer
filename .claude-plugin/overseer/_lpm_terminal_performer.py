"""Fixed-command terminal execution with sanitizer-only incremental output."""

from __future__ import annotations

import codecs
import os
import signal
import stat
import time
from collections.abc import Mapping
from contextlib import suppress
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


def _utf8_decoder() -> codecs.IncrementalDecoder:
    return codecs.getincrementaldecoder("utf-8")()


@dataclass(kw_only=True)
class _TerminalState:
    pid: int
    stdin_descriptor: int
    stdout_descriptor: int
    stderr_descriptor: int
    stdout: str = field(default="", repr=False)
    stderr: str = field(default="", repr=False)
    stdout_decoder: codecs.IncrementalDecoder = field(default_factory=_utf8_decoder, repr=False)
    stderr_decoder: codecs.IncrementalDecoder = field(default_factory=_utf8_decoder, repr=False)
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
        try:
            _read_available(state=state, timeout_seconds=self.read_timeout_seconds)
        except UnicodeDecodeError:
            return _unavailable_observation()
        running, exit_status = _poll(state=state)
        return self.sanitizer.terminal_observation(
            running=running,
            exit_status=exit_status,
            stdout=state.stdout,
            stderr=state.stderr,
        )

    def send_line(self, *, text: str) -> dict[str, object]:
        """Write one already-validated non-secret line without exposing terminal output."""
        state = self._state
        if state is None:
            return _unavailable()
        payload = f"{text}\n".encode()
        sent = 0
        try:
            while sent < len(payload):
                sent += os.write(state.stdin_descriptor, payload[sent:])
        except OSError:
            return _unavailable()
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
    try:
        status = Path(command.path).stat(follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISREG(status.st_mode)
        and status.st_dev == command.device
        and status.st_ino == command.inode
        and os.access(command.path, os.X_OK)
    )


def _spawn(*, command: ExecutionCommand, environ: Mapping[str, str]) -> _TerminalState | None:
    descriptors: list[int] = []
    pid: int | None = None
    try:
        child_stdin, service_stdin = os.pipe2(os.O_CLOEXEC)
        descriptors.extend((child_stdin, service_stdin))
        service_stdout, child_stdout = os.pipe2(os.O_CLOEXEC)
        descriptors.extend((service_stdout, child_stdout))
        service_stderr, child_stderr = os.pipe2(os.O_CLOEXEC)
        descriptors.extend((service_stderr, child_stderr))
        actions = (
            (os.POSIX_SPAWN_DUP2, child_stdin, 0),
            (os.POSIX_SPAWN_DUP2, child_stdout, 1),
            (os.POSIX_SPAWN_DUP2, child_stderr, 2),
            *((os.POSIX_SPAWN_CLOSE, descriptor) for descriptor in descriptors),
        )
        pid = os.posix_spawn(
            command.path,
            (command.path, *command.arguments),
            dict(environ),
            file_actions=actions,
            setpgroup=0,
        )
        os.set_blocking(service_stdout, False)
        os.set_blocking(service_stderr, False)
        for descriptor in (child_stdin, child_stdout, child_stderr):
            _close_descriptor(descriptor=descriptor, descriptors=descriptors)
    except OSError:
        _close_descriptors(descriptors=descriptors)
        if pid is not None:
            _terminate_and_reap(pid=pid)
        return None
    return _TerminalState(
        pid=pid,
        stdin_descriptor=service_stdin,
        stdout_descriptor=service_stdout,
        stderr_descriptor=service_stderr,
    )


def _read_available(*, state: _TerminalState, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        state.stdout_closed, stdout = _drain(
            descriptor=state.stdout_descriptor,
            decoder=state.stdout_decoder,
        )
        state.stdout += stdout
        state.stderr_closed, stderr = _drain(
            descriptor=state.stderr_descriptor,
            decoder=state.stderr_decoder,
        )
        state.stderr += stderr
        changed = state.stdout_closed or bool(stdout)
        changed = changed or state.stderr_closed or bool(stderr)
        if changed or time.monotonic() >= deadline:
            return
        time.sleep(min(0.001, max(0.0, deadline - time.monotonic())))


def _drain(*, descriptor: int, decoder: codecs.IncrementalDecoder) -> tuple[bool, str]:
    pieces: list[str] = []
    while True:
        try:
            chunk = os.read(descriptor, 65536)
        except BlockingIOError:
            return False, "".join(pieces)
        if not chunk:
            pieces.append(decoder.decode(b"", final=True))
            return True, "".join(pieces)
        pieces.append(decoder.decode(chunk))


def _poll(*, state: _TerminalState) -> tuple[bool, int | None]:
    if not state.reaped:
        waited, status = os.waitpid(state.pid, os.WNOHANG)
        if waited != 0:
            state.reaped = True
            state.exit_status = os.waitstatus_to_exitcode(status)
    streams_closed = state.stdout_closed and state.stderr_closed
    return not (state.reaped and streams_closed), state.exit_status


def _close_descriptor(*, descriptor: int, descriptors: list[int]) -> None:
    os.close(descriptor)
    descriptors.remove(descriptor)


def _close_descriptors(*, descriptors: list[int]) -> None:
    for descriptor in descriptors:
        with suppress(OSError):
            os.close(descriptor)


def _terminate_and_reap(*, pid: int) -> None:
    with suppress(OSError):
        os.kill(pid, signal.SIGKILL)
    with suppress(OSError):
        _ = os.waitpid(pid, 0)


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
