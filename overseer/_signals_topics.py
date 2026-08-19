"""Topic-name helpers for supervisor and foreman entity suffixes."""

from __future__ import annotations

__all__: list[str] = [
    "is_foreman_topic",
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
    return topic.lower().endswith(_RESERVED_WORKER_SUFFIXES)


def is_foreman_topic(*, topic: str) -> bool:
    """True when a topic is the reserved foreman entity topic."""
    return topic.lower().endswith(_FOREMAN_SUFFIX)


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
