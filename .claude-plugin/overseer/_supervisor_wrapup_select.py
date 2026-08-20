"""Select the entity-specific wrap-up text for a supervised track."""

from __future__ import annotations

from collections.abc import Callable

import registry
import signals
from _supervisor_prompts import (
    foreman_wrapup_message,
    grooming_wrapup_message,
    supervisor_wrapup_message,
)

__all__: list[str] = ["WorkerWrapup", "select_wrapup_message"]

WorkerWrapup = Callable[[int, str, str, str | None], str]


def select_wrapup_message(
    *, track: registry.Track, remaining: int, worker_wrapup: WorkerWrapup
) -> str:
    """Return the low-context wrap-up matching the track's entity kind."""
    topic = track.topic
    if signals.is_foreman_topic(topic=topic):
        return foreman_wrapup_message(
            remaining=remaining,
            repo=track.repo,
            topic=topic,
            epic=track.epic,
        )
    if signals.is_grooming_topic(topic=topic):
        return grooming_wrapup_message(remaining=remaining, repo=track.repo, topic=topic)
    worker_topic = signals.topic_supervised_worker(topic=topic)
    if worker_topic is not None:
        return supervisor_wrapup_message(
            remaining=remaining,
            repo=track.repo,
            topic=worker_topic,
            epic=track.epic,
        )
    return worker_wrapup(remaining, track.repo, topic, track.epic)
