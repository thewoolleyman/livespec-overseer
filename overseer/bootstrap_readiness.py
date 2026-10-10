"""Bounded fresh observation after a bootstrap daemon launch."""

from __future__ import annotations

import time
from typing import Protocol

import bootstrap

__all__: list[str] = ["DaemonHostObserver", "ReadinessStop", "await_exact_daemon"]


class DaemonHostObserver(Protocol):
    """One fresh exact-instance, pane and process observation."""

    def __call__(self) -> bootstrap.DaemonHostReading: ...


class ReadinessStop(Protocol):
    """Recognize terminal evidence that makes further observation pointless."""

    def __call__(self, *, reading: bootstrap.DaemonHostReading) -> bool: ...


def _never_stop(*, reading: bootstrap.DaemonHostReading) -> bool:
    del reading
    return False


def await_exact_daemon(
    *,
    observe: DaemonHostObserver,
    timeout_seconds: float,
    poll_seconds: float,
    initial: bootstrap.DaemonHostReading | None = None,
    stop: ReadinessStop = _never_stop,
) -> bootstrap.DaemonHostReading:
    """Return the first verified host, or the last unresolved bounded reading."""
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    reading = observe() if initial is None else initial
    while True:
        if stop(reading=reading) or reading.pane_id or time.monotonic() >= deadline:
            return reading
        time.sleep(poll_seconds)
        reading = observe()
