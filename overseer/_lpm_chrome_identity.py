"""Bounded local product-identity probe for an installed Google Chrome executable."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

__all__: list[str] = [
    "is_google_chrome",
]


def is_google_chrome(
    *, executable: Path, environ: Mapping[str, str], timeout_seconds: float
) -> bool:
    """Accept only a zero-exit version response identifying the Google Chrome product."""
    descriptors: list[int] = []
    pid: int | None = None
    try:
        version_read, version_write = os.pipe2(os.O_CLOEXEC)
        descriptors.extend((version_read, version_write))
        null_descriptor = os.open(os.devnull, os.O_RDWR | os.O_CLOEXEC)
        descriptors.append(null_descriptor)
        actions = (
            (os.POSIX_SPAWN_DUP2, null_descriptor, 0),
            (os.POSIX_SPAWN_DUP2, version_write, 1),
            (os.POSIX_SPAWN_DUP2, null_descriptor, 2),
            *((os.POSIX_SPAWN_CLOSE, descriptor) for descriptor in descriptors),
        )
        pid = os.posix_spawn(
            str(executable),
            (str(executable), "--version"),
            dict(environ),
            file_actions=actions,
            setpgroup=0,
        )
        _close_descriptor(descriptor=version_write, descriptors=descriptors)
        _close_descriptor(descriptor=null_descriptor, descriptors=descriptors)
        os.set_blocking(version_read, False)
        output, deadline = bytearray(), time.monotonic() + timeout_seconds
        while True:
            _drain(descriptor=version_read, output=output)
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited != 0:
                pid = None
                break
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.001, max(0.0, deadline - time.monotonic())))
        _drain(descriptor=version_read, output=output)
        product = output.decode("utf-8", errors="replace").strip()
        return os.waitstatus_to_exitcode(status) == 0 and product.startswith("Google Chrome ")
    except OSError:
        return False
    finally:
        _close_descriptors(descriptors=descriptors)
        if pid is not None:
            _terminate_and_reap(pid=pid)


def _drain(*, descriptor: int, output: bytearray) -> None:
    while True:
        try:
            chunk = os.read(descriptor, 4096)
        except BlockingIOError:
            return
        if not chunk:
            return
        output.extend(chunk)


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
