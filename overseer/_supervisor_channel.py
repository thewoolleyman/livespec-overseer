"""_supervisor_channel — the session-bound delivery channel for a daemon message.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. SPECIFICATION v060, contracts.md, the daemon-message delivery channel: the
wrap-up and the keep-going nudge MAY be delivered to a supervised worker through a
direct message channel instead of the ONE atomic paste — but only through a
SUPPORTED one.

A channel is SUPPORTED only when it

a. addresses exactly one session by that session's LIVE SESSION IDENTITY, never by
   topic name, pane or repository;
b. reports, for each message, an explicit acknowledgement that the addressed session
   accepted it; and
c. reports a refusal or an unavailable channel BEFORE transmission distinguishably
   from a loss AFTER transmission.

That three-part test is what :class:`MessageChannel` encodes: a channel that cannot
name the identity it addresses cannot satisfy (a), and one that cannot distinguish
its three outcomes cannot satisfy (b) or (c). A runtime offering nothing that meets
all three delivers by the paste. Claude Code's per-session UDS socket was measured
against version 2.1.170: it addresses a live identity, but its sender resolves when
the socket closes without parsing an acceptance acknowledgement. Its provider thus
returns ``None`` rather than asserting a channel the receiver has not proven it
accepted.

Choosing the channel changes HOW a message is delivered, never WHETHER it is: every
guard that governs the act's paste governs its channel delivery unchanged. This
module therefore holds no policy at all — only the vocabulary, the resolution seam
and the binding proof. The acts themselves stay where they were
(:mod:`_supervisor_wrapup_injection`, :mod:`_supervisor_nudge`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from _claude_peer_channel import claude_peer_channel_provider

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CHANNEL_DELIVERED",
    "CHANNEL_FAILED",
    "CHANNEL_UNCONFIRMED",
    "NUDGE_MESSAGE",
    "WRAPUP_MESSAGE",
    "ChannelProvider",
    "ChannelSend",
    "DeliveryRecord",
    "MessageChannel",
    "channel_provider",
    "delivery_path",
    "resolve_channel",
]

# The two daemon messages this contract governs, named as the row and the log name
# them. The resume prompt, the pair nudge and the picker-stall relay are NOT daemon
# messages under it and never acquire a delivery-path record.
WRAPUP_MESSAGE = "wrap-up"
NUDGE_MESSAGE = "keep-going nudge"

# A channel delivery is DELIVERED only on the channel's acceptance acknowledgement
# for that message, and FAILED only when the channel reports a refusal or an
# unavailable channel BEFORE transmission. Every other outcome — a connection made
# and then lost, a timeout after transmission, an acknowledgement that never arrives
# — is UNCONFIRMED, which is held rather than retried.
CHANNEL_DELIVERED = "delivered"
CHANNEL_FAILED = "failed"
CHANNEL_UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True, kw_only=True)
class ChannelSend:
    """One channel send's outcome, plus the detail the row and the log name it by."""

    outcome: str
    detail: str = ""


@dataclass(frozen=True, kw_only=True)
class DeliveryRecord:
    """WHICH routes one daemon message took this act, and how each of them ended.

    Both halves are carried because an act can take BOTH: a channel that refuses
    before transmission may be followed by the guarded paste in the same act, and the
    contract requires the row and the log to name the failed attempt as well as the
    paste that rescued it. Naming only the surviving route would read as though the
    channel was never tried.
    """

    message: str
    channel: str | None = None
    channel_outcome: str | None = None
    paste_outcome: str | None = None


def delivery_path(*, record: DeliveryRecord) -> str:
    """The one phrase the track's row and the daemon log both name the route by.

    Single-sourced so the two surfaces cannot drift: an operator comparing a row
    against the log is comparing the same string, not two renderings of one fact.
    """
    legs: list[str] = []
    if record.channel is not None:
        legs.append(f"channel {record.channel}: {record.channel_outcome}")
    if record.paste_outcome is not None:
        legs.append(f"paste: {record.paste_outcome}")
    return f"{record.message} via {', then '.join(legs)}"


class MessageChannel(Protocol):
    """One runtime's supported, session-bound channel for a single live session."""

    name: str
    addressed_identity: str | None

    def send(self, *, text: str) -> ChannelSend: ...

    def late_acceptance(self) -> bool: ...


class ChannelProvider(Protocol):
    """Resolve the supported channel for a live session, or ``None`` when none is."""

    def __call__(
        self,
        *,
        sup: Supervisor,
        runtime: str,
        session: str,
        topic: str,
        identity: str | None,
    ) -> MessageChannel | None: ...


# The one resolution seam, a module-level provider in the same shape as
# `_supervisor_wrapup_injection.wrapup_message_provider`. It lives HERE rather than on
# the `Supervisor` dataclass because it is a property of the RUNTIME, not of a daemon
# instance: every track on a given runtime resolves the same way, and the arguments
# below already carry everything a per-session answer needs. Rebind it through this
# module, never through a facade re-export.
channel_provider: ChannelProvider = claude_peer_channel_provider


def resolve_channel(
    *,
    sup: Supervisor,
    runtime: str,
    session: str,
    topic: str,
    identity: str | None,
) -> MessageChannel | None:
    """The supported channel for this pane's live session, or ``None`` for a paste."""
    return channel_provider(
        sup=sup, runtime=runtime, session=session, topic=topic, identity=identity
    )
