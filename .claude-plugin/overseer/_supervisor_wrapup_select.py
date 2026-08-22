"""Select the entity-specific wrap-up text for a supervised track."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import registry
from _supervisor_prompts import (
    foreman_wrapup_message,
    grooming_wrapup_message,
    supervisor_wrapup_message,
)

__all__: list[str] = [
    "WorkerWrapup",
    "select_stranded_ready_notice",
    "select_wrapup_message",
]

WorkerWrapup = Callable[[int, str, str, str | None], str]


def select_wrapup_message(
    *, track: registry.Track, remaining: int, worker_wrapup: WorkerWrapup
) -> str:
    """Return the low-context wrap-up matching the track's entity kind."""
    if isinstance(track, registry.SupervisorSeat):
        return supervisor_wrapup_message(
            remaining=remaining,
            repo=track.repo,
            topic=track.supervised_topic,
            epic=track.epic,
        )
    if isinstance(track, registry.ForemanSeat):
        return foreman_wrapup_message(
            remaining=remaining,
            repo=track.repo,
            topic=track.topic,
            epic=track.epic,
        )
    if isinstance(track, registry.GroomingSeat):
        return grooming_wrapup_message(
            remaining=remaining,
            repo=track.repo,
            topic=track.topic,
        )
    plan_track = cast("registry.PlanTrack", track)
    return worker_wrapup(remaining, plan_track.repo, plan_track.topic, plan_track.epic)


def select_stranded_ready_notice(*, track: registry.Track, age: str, reason: str) -> str:
    """Return the report-only stranded-ready notice matching the track kind."""
    topic = track.supervised_topic if isinstance(track, registry.SupervisorSeat) else track.topic
    return (
        "REPORT-ONLY: your `ready` declaration cannot currently certify for restart.\n"
        f"Track: {track.repo}::{topic}\n"
        f"Age: {age}\n"
        f"Reason: ready cannot certify: {reason}\n\n"
        "This notice authorizes no restart and gives you no new permission to act. "
        "The daemon is only reporting that restart remains held until a future "
        "declaration certifies under a current delivered round."
    )
