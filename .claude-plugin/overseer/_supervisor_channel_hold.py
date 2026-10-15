"""_supervisor_channel_hold — the daemon's side of an UNCONFIRMED channel delivery.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. SPECIFICATION v060, contracts.md, the daemon-message delivery channel.

A channel reports three outcomes, and the awkward one is the third. DELIVERED and
FAILED are both decisions the daemon can act on; UNCONFIRMED is the honest absence of
one — a connection made and then lost, a timeout after transmission, an
acknowledgement that never arrived. The message may be sitting in the session's
input, or it may have evaporated, and nothing the daemon can observe at that instant
tells it which.

So it is HELD rather than guessed about: never sent again by either path, and while
it stands no LATER daemon message reaches that session either. The hold is against
the session, not against the message, because the hazard is a second wind-down
arriving behind a first one that did land. It is surfaced with its age so a hold that
never resolves cannot sit unseen, and `_registry_channel_hold` keeps it durable so a
daemon bounce — precisely when an in-memory hold would be lost — cannot release it by
forgetting.

The release rules live here rather than in the store because each of them is a
JUDGEMENT about observed evidence, which is this layer's business and not the
sidecar's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
from _supervisor_liveness_time import age_label

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "held_delivery",
    "record_unconfirmed",
    "surface_hold",
]


def held_delivery(*, sup: Supervisor, track: registry.Track) -> registry.ChannelHold | None:
    """This track's standing unconfirmed delivery, or None when nothing is held."""
    return registry.read_channel_hold(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)


def record_unconfirmed(
    *,
    sup: Supervisor,
    track: registry.Track,
    message: str,
    channel: str,
    identity: str | None,
    pane_was_busy: bool,
) -> None:
    """Hold an unconfirmed delivery, recording what a later release has to judge."""
    registry.record_channel_hold(
        repo=track.repo,
        topic=track.topic,
        hold=registry.ChannelHold(
            message=message,
            channel=channel,
            session_identity=identity,
            held_at=sup.now(),
            pane_was_busy=pane_was_busy,
        ),
        stamp_path=sup.stamp_path,
    )


def surface_hold(
    *,
    sup: Supervisor,
    track: registry.Track,
    hold: registry.ChannelHold,
    pane: str,
) -> None:
    """Report a withheld daemon message, naming the hold and HOW OLD it is.

    The age is the operator's whole handle on this state: a hold seconds old is the
    protocol working, and the same hold hours old is a channel that swallowed a
    wind-down and a track quietly going unsupervised.
    """
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=track.tmux or track.topic,
        pane=pane,
        message=(
            f"daemon message WITHHELD: a {hold.message} sent through channel "
            f"{hold.channel} {age_label(seconds=max(0.0, sup.now() - hold.held_at))} ago "
            f"was never acknowledged, so it is held and nothing later is delivered to "
            f"this session by either path until it is released"
        ),
        condition="channel-delivery-held",
    )
