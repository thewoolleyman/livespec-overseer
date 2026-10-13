"""Bounded local product-identity probe for an installed Google Chrome executable."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Mapping
from pathlib import Path

__all__: list[str] = [
    "is_google_chrome",
]


def is_google_chrome(
    *, executable: Path, environ: Mapping[str, str], timeout_seconds: float
) -> bool:
    """Accept only a zero-exit version response identifying the Google Chrome product."""
    version_read, version_write = os.pipe2(os.O_CLOEXEC)
    null_descriptor = os.open(os.devnull, os.O_RDWR | os.O_CLOEXEC)
    descriptors = (version_read, version_write, null_descriptor)
    actions = (
        (os.POSIX_SPAWN_DUP2, null_descriptor, 0),
        (os.POSIX_SPAWN_DUP2, version_write, 1),
        (os.POSIX_SPAWN_DUP2, null_descriptor, 2),
        *((os.POSIX_SPAWN_CLOSE, descriptor) for descriptor in descriptors),
    )
    try:
        pid = os.posix_spawn(
            str(executable),
            (str(executable), "--version"),
            dict(environ),
            file_actions=actions,
            setpgroup=0,
        )
    except OSError:
        _close_descriptors(descriptors=descriptors)
        return False
    _close_descriptors(descriptors=(version_write, null_descriptor))
    os.set_blocking(version_read, False)
    output = bytearray()
    deadline = time.monotonic() + timeout_seconds
    while True:
        _drain(descriptor=version_read, output=output)
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited != 0:
            break
        if time.monotonic() >= deadline:
            os.kill(pid, signal.SIGKILL)
            _ = os.waitpid(pid, 0)
            os.close(version_read)
            return False
        time.sleep(min(0.001, max(0.0, deadline - time.monotonic())))
    _drain(descriptor=version_read, output=output)
    os.close(version_read)
    product = output.decode("utf-8", errors="replace").strip()
    return os.waitstatus_to_exitcode(status) == 0 and product.startswith("Google Chrome ")


def _drain(*, descriptor: int, output: bytearray) -> None:
    while True:
        try:
            chunk = os.read(descriptor, 4096)
        except BlockingIOError:
            return
        if not chunk:
            return
        output.extend(chunk)


def _close_descriptors(*, descriptors: tuple[int, ...]) -> None:
    for descriptor in descriptors:
        os.close(descriptor)
