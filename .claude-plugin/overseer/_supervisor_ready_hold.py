"""Bounded event history for ready declarations held by restart safety guards."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_config
import signals

if TYPE_CHECKING:
    import registry
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = ["ReadyHoldRequest", "condition", "report"]

_BACKGROUND_WAIT_RE = re.compile(r"Waiting for \d+ background", re.IGNORECASE)


@dataclass(frozen=True, kw_only=True)
class ReadyHoldRequest:
    sup: Supervisor
    track: registry.Track
    obs: Observation
    status: str
    unsettled: bool


def _busy_condition(*, request: ReadyHoldRequest) -> str:
    capture = request.obs.capture
    background_wait = _BACKGROUND_WAIT_RE.search(capture) is not None
    pane_spinner = signals.is_busy(capture_text=capture) and not background_wait
    session_status = request.obs.claude_status
    idle_harness_status = request.obs.idle and not (background_wait or pane_spinner)
    session_detail = f"busy: session-file status {session_status}"
    explicit_harness_status = (
        f"{session_detail} while pane shows an idle composer with no spinner or background wait"
    )
    choices = (
        ("busy: pane spinner", 1),
        ("busy: background wait (process fallback)", 2 * int(request.obs.codex_fallback)),
        (session_detail, 3 * int(session_status in {"busy", "shell"})),
        (
            explicit_harness_status,
            4 * int(session_status in {"busy", "shell"} and idle_harness_status),
        ),
        ("busy: pane spinner", 5 * int(pane_spinner)),
        ("busy: background wait", 6 * int(background_wait)),
    )
    return max(choices, key=lambda choice: choice[1])[0]


def condition(*, request: ReadyHoldRequest) -> str | None:
    """Name the first restart guard still holding this ready declaration."""
    choices = (
        (None, 0),
        ("pane-identity mismatch", int(request.status == "settling")),
        ("unsettled", 2 * int(request.unsettled)),
        ("not-idle", 3 * int(not request.obs.idle)),
        (_busy_condition(request=request), 4 * int(request.obs.busy)),
    )
    return max(choices, key=lambda choice: choice[1])[0]


def report(*, request: ReadyHoldRequest) -> None:
    """Log a continuous ready hold after its floor, rate-limited by a fixed window."""
    current = condition(request=request)
    state = request.obs.istate
    now = request.obs.observed_at
    changed = current != state.ready_hold_condition
    previous_since = state.ready_hold_since if state.ready_hold_since is not None else now
    state.ready_hold_condition = current
    state.ready_hold_since = now if changed else previous_since
    state.ready_hold_last_reported = None if changed else state.ready_hold_last_reported
    last_reported = state.ready_hold_last_reported
    due = all(
        (
            current is not None,
            now - state.ready_hold_since >= _supervisor_config.READY_HOLD_REPORT_AFTER,
            last_reported is None
            or now - last_reported >= _supervisor_config.READY_HOLD_REPORT_WINDOW,
        )
    )
    if due:
        request.sup.log(
            event="ready-replacement-held",
            repo=request.track.repo,
            topic=request.track.topic,
            fields={"holding_condition": current},
            message=(
                f"ready replacement held for {request.track.repo}::{request.track.topic}: {current}"
            ),
        )
        state.ready_hold_last_reported = now
