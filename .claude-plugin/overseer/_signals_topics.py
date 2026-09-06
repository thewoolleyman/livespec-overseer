"""Topic-name helpers for supervisor entity suffixes."""

from __future__ import annotations

__all__: list[str] = [
    "is_foreman_topic",
    "reserved_worker_kind",
    "reserved_worker_suffix",
    "supervisor_entity_topic",
    "supervisor_topic",
    "topic_reserved_for_supervisor",
    "topic_supervised_worker",
]

_SUPERVISOR_SUFFIX = "-supervisor"
# Retained for the caam account-rotation loop ALONE (bucket 1). The foreman SEAT is
# gone, so `-foreman` is no longer a reserved worker suffix and no seat is derived
# from it; SPECIFICATION/spec.md still points a session whose name carries this
# suffix at the scoped model, and that exact-suffix match is the only surviving
# reader. With no foreman sessions it matches nothing.
_FOREMAN_SUFFIX = "-foreman"
_RESERVED_WORKER_KINDS = {
    _SUPERVISOR_SUFFIX: "supervisor",
}


def topic_reserved_for_supervisor(*, topic: str) -> bool:
    """True when a worker topic would collide with the reserved pair namespace."""
    return reserved_worker_suffix(topic=topic) is not None


def reserved_worker_suffix(*, topic: str) -> str | None:
    """The reserved worker-topic suffix matched by ``topic``, if any."""
    if topic.lower().endswith(_SUPERVISOR_SUFFIX):
        return _SUPERVISOR_SUFFIX
    return None


def reserved_worker_kind(*, topic: str) -> str | None:
    """The reserved worker-topic kind matched by ``topic``, if any."""
    suffix = reserved_worker_suffix(topic=topic)
    return None if suffix is None else _RESERVED_WORKER_KINDS[suffix]


def is_foreman_topic(*, topic: str) -> bool:
    """True when a session name carries the caam-matched foreman suffix."""
    return topic.lower().endswith(_FOREMAN_SUFFIX)


def supervisor_entity_topic(*, topic: str) -> str:
    """The suffixed entity name for a worker topic's supervisor pair member."""
    return f"{topic}{_SUPERVISOR_SUFFIX}"


def supervisor_topic(*, entity_topic: str) -> str:
    """The worker topic owned by a suffixed supervisor entity topic."""
    if not entity_topic.lower().endswith(_SUPERVISOR_SUFFIX):
        return entity_topic
    return entity_topic[: -len(_SUPERVISOR_SUFFIX)]


def topic_supervised_worker(*, topic: str) -> str | None:
    """The worker topic a `-supervisor`-suffixed entity topic supervises.

    Precise about the SUFFIX: returns None for a plain worker topic, never a
    mis-stripped string.
    """
    if not topic.lower().endswith(_SUPERVISOR_SUFFIX):
        return None
    return topic[: -len(_SUPERVISOR_SUFFIX)]
