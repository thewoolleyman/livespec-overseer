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
all three delivers by the paste, which is why :func:`no_supported_channel` — the
default provider — is the honest answer rather than a stub: no runtime this daemon
drives has a measured channel yet, and a channel asserted rather than measured would
route a wind-down into a transport nobody has proven accepts it.

Choosing the channel changes HOW a message is delivered, never WHETHER it is: every
guard that governs the act's paste governs its channel delivery unchanged. This
module therefore holds no policy at all — only the vocabulary, the resolution seam
and the binding proof. The acts themselves stay where they were
(:mod:`_supervisor_wrapup_injection`, :mod:`_supervisor_nudge`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "CHANNEL_DELIVERED",
    "CHANNEL_FAILED",
    "CHANNEL_UNCONFIRMED",
    "ChannelProvider",
    "ChannelSend",
    "MessageChannel",
    "channel_provider",
    "no_supported_channel",
    "resolve_channel",
]

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


def no_supported_channel(
    *,
    sup: Supervisor,
    runtime: str,
    session: str,
    topic: str,
    identity: str | None,
) -> MessageChannel | None:
    """The default provider: no runtime offers a channel meeting all three tests.

    Deliberately NOT a speculative transport. The candidate channels named by the
    maintainer — herdr's ``agent prompt``, Claude Code's per-session peer socket,
    Codex's app-server — each fail or cannot be measured from here: ``agent prompt``
    addresses a PANE and types into it, and the other two exist only on the operator
    host. Returning ``None`` makes every runtime paste exactly as it did before,
    which is the contract's own answer for a runtime with no supported channel.
    """
    del sup, runtime, session, topic, identity
    return None


# The one resolution seam, a module-level provider in the same shape as
# `_supervisor_wrapup_injection.wrapup_message_provider`. It lives HERE rather than on
# the `Supervisor` dataclass because it is a property of the RUNTIME, not of a daemon
# instance: every track on a given runtime resolves the same way, and the arguments
# below already carry everything a per-session answer needs. Rebind it through this
# module, never through a facade re-export.
channel_provider: ChannelProvider = no_supported_channel


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
