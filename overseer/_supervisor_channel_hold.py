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

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_channel
import registry
from _supervisor_liveness_time import age_label

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "HoldRelease",
    "held_delivery",
    "record_unconfirmed",
    "release_reason",
    "release_resolved_hold",
    "surface_hold",
]


def held_delivery(*, sup: Supervisor, track: registry.Track) -> registry.ChannelHold | None:
    """This track's standing unconfirmed delivery, or None when nothing is held."""
    return registry.read_channel_hold(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)


def record_unconfirmed(  # noqa: PLR0913 — one hold site; the release needs every fact
    *,
    sup: Supervisor,
    track: registry.Track,
    message: str,
    channel: str,
    identity: str | None,
    pane_was_busy: bool,
    bands: tuple[int, ...] = (),
    compaction_latched_at: float | None = None,
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
            bands=bands,
            compaction_latched_at=compaction_latched_at,
        ),
        stamp_path=sup.stamp_path,
    )


@dataclass(frozen=True, kw_only=True)
class HoldRelease:
    """Why a hold may be released, and whether that release DELIVERS its message.

    The two halves are genuinely independent, which is why this is not just a reason
    string. Two of the rules are positive evidence that the session took the message,
    so the delivery becomes DELIVERED and the round it answered must be marked. The
    nudge's episode-end rule is not evidence of anything — it only bounds a hold that
    can no longer be resolved — so it frees the track without claiming delivery.
    """

    reason: str
    delivered: bool


def release_reason(
    *,
    hold: registry.ChannelHold,
    late_accepted: bool,
    pane_busy: bool,
    idle: bool,
) -> HoldRelease | None:
    """Why this hold may be released NOW, or None to leave it standing.

    A pure predicate over evidence the caller has already observed, so the rules can
    be read — and driven — without a live pane. Each carries the phrase the daemon log
    reports, because an operator who sees a hold disappear needs to know WHICH rule
    freed it: "the channel answered late" and "the session took a turn" are very
    different stories about the same delivery.

    The round-close rule is NOT here, and deliberately: the hold shares the round's
    sidecar entry, so closing the round takes the hold with it structurally. A copy of
    that rule in this function would be a second mechanism that could disagree.
    """
    if late_accepted:
        return HoldRelease(reason="a late acceptance acknowledgement arrived", delivered=True)
    if pane_busy and not hold.pane_was_busy:
        # A turn that began after the send is evidence the session took the message.
        # On a pane that was ALREADY busy the turn in flight proves nothing about THIS
        # delivery, which is the whole reason the hold records `pane_was_busy`.
        return HoldRelease(
            reason="a turn started after the send on a pane that was not already busy",
            delivered=True,
        )
    if hold.message == _supervisor_channel.NUDGE_MESSAGE and not idle:
        # A nudge opens no round, so a round close cannot free it. The episode it
        # answered is its bound — and an episode can end WITHOUT a turn starting (the
        # session declares `blocked`, a gate opens), which is why this is its own rule.
        # Nothing here says the nudge LANDED, so this release delivers nothing.
        return HoldRelease(reason="the idle episode the nudge answered ended", delivered=False)
    return None


def release_resolved_hold(
    *,
    sup: Supervisor,
    track: registry.Track,
    is_codex: bool,
    pane_busy: bool,
    idle: bool,
) -> None:
    """Free this track's held delivery once the daemon can read how it ended.

    Runs once per tick from the evaluation's reconcile phase, BEFORE the guard
    cascade, for the same reason the late-Codex reconciliation does: the acts that
    consult the hold decide on facts gathered in that phase, so a hold released
    afterwards would still read as standing and would withhold a message that is
    owed. Releasing first means this same tick sees the freed track.
    """
    hold = held_delivery(sup=sup, track=track)
    if hold is None:
        return
    release = release_reason(
        hold=hold,
        late_accepted=_late_accepted(sup=sup, track=track, hold=hold, is_codex=is_codex),
        pane_busy=pane_busy,
        idle=idle,
    )
    if release is None:
        return
    registry.clear_channel_hold(repo=track.repo, topic=track.topic, stamp_path=sup.stamp_path)
    if release.delivered:
        _mark_held_delivery_landed(sup=sup, track=track, hold=hold)
    sup.log(
        message=(
            f"released held {hold.message} for {track.repo}::{track.topic} "
            f"(channel {hold.channel}; {release.reason}; "
            f"{'DELIVERED' if release.delivered else 'undelivered'})"
        )
    )


def _mark_held_delivery_landed(
    *, sup: Supervisor, track: registry.Track, hold: registry.ChannelHold
) -> None:
    """Mark the round the released delivery answered, so it is never sent again.

    Freeing the hold without this would re-open the very hazard the hold exists to
    close: the bands stay unnotified, the same wrap-up is due on the next tick, and
    the daemon re-sends a message it has just been told the session accepted. The
    marking is what converts "released" into "DELIVERED".
    """
    for band in hold.bands:
        registry.add_notified_band(
            repo=track.repo, topic=track.topic, band=band, stamp_path=sup.stamp_path
        )
    if hold.compaction_latched_at is not None:
        registry.mark_compaction_rearmed(
            repo=track.repo,
            topic=track.topic,
            latched_at=hold.compaction_latched_at,
            stamp_path=sup.stamp_path,
        )


def _late_accepted(
    *,
    sup: Supervisor,
    track: registry.Track,
    hold: registry.ChannelHold,
    is_codex: bool,
) -> bool:
    """Has the channel that swallowed this delivery since acknowledged it?

    Asked of the channel the runtime resolves RIGHT NOW, and only when that is still
    the same named channel the hold was recorded against. A different channel cannot
    speak for a message it never carried, and a runtime that has stopped offering one
    at all simply has no late answer — neither case releases the hold, which then
    waits for a turn, its round, or its episode.
    """
    channel = _supervisor_channel.resolve_channel(
        sup=sup,
        runtime="codex" if is_codex else "claude",
        session=track.tmux or track.topic,
        topic=track.topic,
        identity=hold.session_identity,
    )
    if channel is None or channel.name != hold.channel:
        return False
    return channel.late_acceptance()


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
