"""Bounded capture observation shared by native prompt submission operations."""

from __future__ import annotations

from collections.abc import Callable

import pane_router_reads
import pane_router_submit_signals

__all__: list[str] = ["observe_capture"]

OBSERVE_ATTEMPTS = 3
OBSERVE_INTERVAL = 0.5


def observe_capture(
    *,
    reads: pane_router_reads.PaneRoutingReads,
    session: str,
    sleep: Callable[[float], None],
    accept: pane_router_submit_signals.CapturePredicate,
) -> str:
    """Read until the requested prompt fact appears or the bound expires."""
    capture = ""
    for attempt in range(OBSERVE_ATTEMPTS):
        capture = reads.capture_pane(session=session)
        if accept(capture=capture):
            break
        if attempt + 1 < OBSERVE_ATTEMPTS:
            sleep(OBSERVE_INTERVAL)
    return capture
