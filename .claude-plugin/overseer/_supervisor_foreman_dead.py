"""Dead-loop escalation policy for foreman heartbeat rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import foreman_stop_state
import registry
from _supervisor_view import RowView

__all__: list[str] = [
    "FOREMAN_HEARTBEAT_COMPLETED_STATUS",
    "FOREMAN_HEARTBEAT_DEAD_STATUS",
    "FOREMAN_HEARTBEAT_HELD_STATUS",
    "FOREMAN_HEARTBEAT_STALE_STATUS",
    "HeartbeatDisposition",
    "dead_loop_escalated",
    "heartbeat_disposition",
    "heartbeat_row",
]

FOREMAN_HEARTBEAT_COMPLETED_STATUS = "foreman-heartbeat-completed"
FOREMAN_HEARTBEAT_DEAD_STATUS = "foreman-heartbeat-dead"
FOREMAN_HEARTBEAT_HELD_STATUS = "foreman-heartbeat-held"
FOREMAN_HEARTBEAT_STALE_STATUS = "foreman-heartbeat-stale"
_DEAD_ESCALATION_MULTIPLIER = 3.0
_RESTORE_PATH_NOTE = "restore: run foreman-runtime --resume, then re-arm the hourly schedule"


@dataclass(frozen=True, kw_only=True)
class HeartbeatDisposition:
    status: str
    reason: str
    human_wait: bool


class HeartbeatSnapshot(Protocol):
    @property
    def pid(self) -> int: ...

    @property
    def tick_generation(self) -> int: ...

    @property
    def tick_interval_seconds(self) -> float: ...


_STOPPED_DISPOSITIONS = {
    foreman_stop_state.FOREMAN_STOP_HELD: HeartbeatDisposition(
        status=FOREMAN_HEARTBEAT_HELD_STATUS, reason="", human_wait=True
    ),
    foreman_stop_state.FOREMAN_STOP_COMPLETED: HeartbeatDisposition(
        status=FOREMAN_HEARTBEAT_COMPLETED_STATUS, reason="", human_wait=False
    ),
}


def dead_loop_escalated(*, age_seconds: float, stale_after_seconds: float) -> bool:
    return age_seconds >= (stale_after_seconds * _DEAD_ESCALATION_MULTIPLIER)


def heartbeat_disposition(
    *, state: str, reason: str, age_seconds: float, stale_after_seconds: float
) -> HeartbeatDisposition:
    stopped = _STOPPED_DISPOSITIONS.get(state)
    if stopped is not None:
        return HeartbeatDisposition(
            status=stopped.status, reason=reason, human_wait=stopped.human_wait
        )
    if dead_loop_escalated(age_seconds=age_seconds, stale_after_seconds=stale_after_seconds):
        return HeartbeatDisposition(
            status=FOREMAN_HEARTBEAT_DEAD_STATUS,
            reason=f"{reason}; {_RESTORE_PATH_NOTE}",
            human_wait=False,
        )
    return HeartbeatDisposition(
        status=FOREMAN_HEARTBEAT_STALE_STATUS, reason=reason, human_wait=False
    )


def heartbeat_row(
    *,
    repo: str,
    age_seconds: float,
    state: str,
    reason: str,
    heartbeat: HeartbeatSnapshot,
    stale_after_seconds: float,
) -> RowView:
    topic = "foreman"
    disposition = heartbeat_disposition(
        state=state, reason=reason, age_seconds=age_seconds, stale_after_seconds=stale_after_seconds
    )
    return RowView(
        topic=topic,
        repo=repo,
        tmux=f"{registry.repo_slug(repo=repo)}-{topic}",
        ctx=None,
        status=disposition.status,
        note=(
            f"foreman heartbeat stale {int(age_seconds // 60)}m; state {state}; "
            f"reason {disposition.reason}; pid {heartbeat.pid}; "
            f"tick {heartbeat.tick_generation}; "
            f"interval {_interval_label(interval=heartbeat.tick_interval_seconds)}s"
        ),
        human_wait=disposition.human_wait,
    )


def _interval_label(*, interval: float) -> str:
    return f"{interval:.3f}".rstrip("0").rstrip(".")
