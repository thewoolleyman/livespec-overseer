"""Durable deduplication records for rejected-state recovery notices."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import jsonio
from _registry_core import atomic_write, file_lock, resolve_stamp_store
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = [
    "RejectedStateNotice",
    "read_rejected_state_notice",
    "record_rejected_state_notice",
    "rejected_value_digest",
]


@dataclass(frozen=True, kw_only=True)
class RejectedStateNotice:
    """The durable delivery history for one rendered rejected value."""

    digest: str
    noticed_at: float
    renoticed: bool


def rejected_value_digest(*, value: str) -> str:
    """Return the stable deduplication identity for the rendered safe value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_rejected_state_notice(
    *, repo: str, topic: str, value: str, stamp_path: str | os.PathLike[str] | None = None
) -> RejectedStateNotice | None:
    """Read the retained delivery history for this track's rendered value, if usable."""
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    entry = jsonio.as_object(value=data.get(stamp_key(repo=repo, topic=topic)))
    history = jsonio.as_object(value=entry.get("rejected_state_notice")) if entry else None
    digest = rejected_value_digest(value=value)
    notice = jsonio.as_object(value=history.get(digest)) if history else None
    noticed_at = jsonio.as_float(value=notice.get("noticed_at")) if notice else None
    if notice is None or noticed_at is None:
        return None
    return RejectedStateNotice(
        digest=digest,
        noticed_at=noticed_at,
        renoticed=notice.get("renoticed") is True,
    )


def record_rejected_state_notice(
    *,
    repo: str,
    topic: str,
    value: str,
    noticed_at: float,
    stamp_path: str | os.PathLike[str] | None = None,
) -> RejectedStateNotice:
    """Record a delivery, preserving its first timestamp for the single re-notice."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    digest = rejected_value_digest(value=value)
    prior = read_rejected_state_notice(repo=repo, topic=topic, value=value, stamp_path=path)
    notice = RejectedStateNotice(
        digest=digest,
        noticed_at=prior.noticed_at if prior is not None else noticed_at,
        renoticed=prior is not None,
    )
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        history = jsonio.as_object(value=current.get("rejected_state_notice"))
        retained = dict(history) if history is not None else {}
        retained[digest] = {"noticed_at": notice.noticed_at, "renoticed": notice.renoticed}
        current["rejected_state_notice"] = retained
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
    return notice
