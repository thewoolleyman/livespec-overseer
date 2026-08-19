"""Topic-name helpers for supervisor and foreman entity suffixes."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = [
    "foreman_seat_accepts_explicit_epic",
    "is_foreman_topic",
    "reserved_worker_suffix",
    "supervisor_entity_topic",
    "supervisor_topic",
    "topic_reserved_for_supervisor",
    "topic_supervised_worker",
]

_SUPERVISOR_SUFFIX = "-supervisor"
_FOREMAN_SUFFIX = "-foreman"
_RESERVED_WORKER_SUFFIXES = (_SUPERVISOR_SUFFIX, _FOREMAN_SUFFIX)
_FOREMAN_TOPIC_ERROR = "reserved -foreman topic has no supervised worker"


def topic_reserved_for_supervisor(*, topic: str) -> bool:
    """True when a worker topic would collide with the reserved pair namespace."""
    return reserved_worker_suffix(topic=topic) is not None


def reserved_worker_suffix(*, topic: str) -> str | None:
    """The reserved worker-topic suffix matched by ``topic``, if any."""
    topic_lower = topic.lower()
    if topic_lower.endswith(_FOREMAN_SUFFIX):
        return _FOREMAN_SUFFIX
    if topic_lower.endswith(_SUPERVISOR_SUFFIX):
        return _SUPERVISOR_SUFFIX
    return None


def is_foreman_topic(*, topic: str) -> bool:
    """True when a topic is the reserved foreman entity topic."""
    return topic.lower().endswith(_FOREMAN_SUFFIX)


def foreman_seat_accepts_explicit_epic(*, repo: str, topic: str, epic: str | None) -> bool:
    """True for the repo's reserved foreman seat when the operator supplied an epic."""
    return (
        epic is not None and is_foreman_topic(topic=topic) and topic == f"{Path(repo).name}-foreman"
    )


def supervisor_entity_topic(*, topic: str) -> str:
    """The suffixed entity name for a worker topic's supervisor pair member."""
    return f"{topic}{_SUPERVISOR_SUFFIX}"


def supervisor_topic(*, entity_topic: str) -> str:
    """The worker topic owned by a suffixed supervisor entity topic."""
    if is_foreman_topic(topic=entity_topic):
        raise ValueError(_FOREMAN_TOPIC_ERROR)
    if not entity_topic.lower().endswith(_SUPERVISOR_SUFFIX):
        return entity_topic
    return entity_topic[: -len(_SUPERVISOR_SUFFIX)]


def topic_supervised_worker(*, topic: str) -> str | None:
    """The worker topic a `-supervisor`-suffixed entity topic supervises.

    Precise about the SUFFIX: returns None for a plain worker topic AND for a
    `-foreman`-suffixed one (foreman entities have no supervised-worker counterpart),
    never a mis-stripped string.
    """
    if not topic.lower().endswith(_SUPERVISOR_SUFFIX):
        return None
    return topic[: -len(_SUPERVISOR_SUFFIX)]
