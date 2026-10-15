"""_registry_channel_hold — the durable record of one UNCONFIRMED channel delivery.

A private collaborator of :mod:`registry`; see that module's header for the whole
split. SPECIFICATION v060, contracts.md, the daemon-message delivery channel: a
channel delivery whose acceptance acknowledgement never arrived is HELD. It is never
sent again by either path, and while it is held no later daemon message reaches that
session at all.

**Durable, and in the ROUND SIDECAR rather than in memory.** The thing a hold
prevents is a second delivery of a message that may already have landed, and a daemon
bounce is exactly when an in-memory hold would be lost and the duplicate sent. It
shares the sidecar entry with the round because the wrap-up's hold is released when
its round closes, so the two facts already live and die together; a keep-going nudge
opens no round and is released by its own idle episode ending instead.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import jsonio
from _registry_core import (
    atomic_write,
    file_lock,
    resolve_stamp_store,
)
from _registry_stamp_core import read_stamp_data, stamp_key

__all__: list[str] = [
    "ChannelHold",
    "read_channel_hold",
    "record_channel_hold",
]


@dataclass(frozen=True, kw_only=True)
class ChannelHold:
    """One unconfirmed channel delivery, held against every later daemon message.

    ``pane_was_busy`` is part of the record rather than re-derived later because the
    release rule depends on it: a turn observed STARTING after the send is evidence
    the session accepted the message, but only on a pane that was not already busy —
    on a busy pane the turn in flight proves nothing about this delivery.
    """

    message: str
    channel: str
    session_identity: str | None
    held_at: float
    pane_was_busy: bool


def read_channel_hold(
    *,
    repo: str,
    topic: str,
    stamp_path: str | os.PathLike[str] | None = None,
) -> ChannelHold | None:
    """The track's held channel delivery, or None when nothing is held.

    Fail-soft toward NO HOLD on a malformed record, matching every other reader in
    this sidecar: an unreadable hold must not wedge a track's daemon messages
    forever, and the delivery it guarded is re-attempted rather than lost.
    """
    data = read_stamp_data(path=resolve_stamp_store(stamp_path=stamp_path))
    entry = jsonio.as_object(value=data.get(stamp_key(repo=repo, topic=topic)))
    held = jsonio.as_object(value=entry.get("channel_hold")) if entry else None
    if held is None:
        return None
    message, channel = held.get("message"), held.get("channel")
    held_at = jsonio.as_float(value=held.get("held_at"))
    identity = held.get("session_identity")
    if not isinstance(message, str) or not isinstance(channel, str) or held_at is None:
        return None
    return ChannelHold(
        message=message,
        channel=channel,
        session_identity=identity if isinstance(identity, str) else None,
        held_at=held_at,
        pane_was_busy=held.get("pane_was_busy") is True,
    )


def record_channel_hold(
    *,
    repo: str,
    topic: str,
    hold: ChannelHold,
    stamp_path: str | os.PathLike[str] | None = None,
) -> None:
    """Persist an unconfirmed channel delivery as this track's standing hold."""
    path = resolve_stamp_store(stamp_path=stamp_path)
    with file_lock(target=path):
        data = read_stamp_data(path=path)
        key = stamp_key(repo=repo, topic=topic)
        entry = jsonio.as_object(value=data.get(key))
        current = dict(entry) if entry is not None else {}
        current["channel_hold"] = {
            "channel": hold.channel,
            "held_at": float(hold.held_at),
            "message": hold.message,
            "pane_was_busy": hold.pane_was_busy,
            "session_identity": hold.session_identity,
        }
        data[key] = current
        atomic_write(path=path, body=json.dumps(data, indent=2, sort_keys=True) + "\n")
