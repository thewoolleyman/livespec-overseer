"""_supervisor_channel_delivery — carry ONE daemon message, by channel or by paste.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. SPECIFICATION v060, contracts.md, the daemon-message delivery channel.

This is the seam between the two ACTS that owe a daemon message — the escalating
wrap-up (:mod:`_supervisor_wrapup_injection`) and the keep-going nudge
(:mod:`_supervisor_nudge`) — and the ROUTE one takes. The acts own WHETHER a message
is owed and every guard that authorizes it; this module owns only HOW the owed
message travels and how that route is reported. Choosing the channel changes HOW a
message is delivered, never WHETHER it is, so nothing here may refuse an act the
caller's guards have already authorized.

It lives apart from either act because both need it identically: a shared outcome
vocabulary, one resolution of the supported channel, and ONE rendering of the route
for the track's row and the daemon log. Folding it into the wrap-up would leave the
nudge reporting its route in a second, drifting dialect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_channel
import _supervisor_launch
import _supervisor_ready
import _supervisor_records
import registry
from _supervisor_config import track_key

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "DeliveryOutcome",
    "DeliveryRequest",
    "binding_proven",
    "deliver",
    "live_identity",
    "paste_outcome",
    "record_delivery",
    "resolve_bound_channel",
]


@dataclass(frozen=True, kw_only=True)
class DeliveryRequest:
    """One owed daemon message, with the facts a route needs to carry it."""

    sup: Supervisor
    track: registry.Track
    target: str
    text: str
    kind: str
    is_codex: bool


@dataclass(frozen=True, kw_only=True)
class DeliveryOutcome:
    """Whether the message landed, whether its effect is unknown, and its route.

    ``submitted`` and ``effect_unknown`` are exactly the pair the guarded paste has
    always returned, so a caller's success, retry and roll-back handling is identical
    whichever route ran. ``record`` is the reporting half and authorizes nothing.
    """

    submitted: bool
    effect_unknown: bool
    record: _supervisor_channel.DeliveryRecord


def paste_outcome(*, submitted: bool, effect_unknown: bool) -> str:
    """A paste's outcome in the same three-value vocabulary a channel send reports.

    A paste whose effect is UNKNOWN is not a failure (v059), and the row must not
    report it as one — so the two vocabularies are shared rather than parallel, and
    an operator reading a row never has to know which route produced the word.
    """
    if submitted:
        return _supervisor_channel.CHANNEL_DELIVERED
    return (
        _supervisor_channel.CHANNEL_UNCONFIRMED
        if effect_unknown
        else _supervisor_channel.CHANNEL_FAILED
    )


def _runtime_of(*, is_codex: bool) -> str:
    return "codex" if is_codex else "claude"


def binding_proven(*, channel: _supervisor_channel.MessageChannel, identity: str | None) -> bool:
    """Is the channel's addressed session PROVABLY the session this act targets?

    Fail-closed on BOTH unknowns, which is the whole point of stating it as a proof
    rather than as a mismatch test: an act whose target identity could not be
    resolved, and a channel that will not name the session it addresses, are each
    "cannot be proven equal" — and a daemon message delivered to a session the
    daemon cannot name is exactly the confusion the live-identity requirement exists
    to prevent.
    """
    return (
        identity is not None
        and channel.addressed_identity is not None
        and channel.addressed_identity == identity
    )


def resolve_bound_channel(
    *, request: DeliveryRequest, identity: str | None
) -> tuple[_supervisor_channel.MessageChannel | None, bool]:
    """``(channel, cancelled)`` — the channel to use, or an act to abandon this tick.

    Three answers, not two. ``(None, False)`` is "no supported channel; paste as
    before". ``(channel, False)`` is a proven binding. ``(None, True)`` is a channel
    whose addressed session cannot be proven to be this act's target, which cancels
    the WHOLE act for the tick — the paste included — so a mismatched identity never
    degrades into typing the message into the pane anyway.
    """
    channel = _supervisor_channel.resolve_channel(
        sup=request.sup,
        runtime=_runtime_of(is_codex=request.is_codex),
        session=_supervisor_launch.session_of(sup=request.sup, track=request.track),
        topic=request.track.topic,
        identity=identity,
    )
    if channel is None:
        return None, False
    if binding_proven(channel=channel, identity=identity):
        return channel, False
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=_supervisor_launch.session_of(sup=request.sup, track=request.track),
        pane=request.target,
        message=(
            f"{request.kind} act CANCELLED this tick: the channel addresses "
            f"{channel.addressed_identity!r}, not the targeted session "
            f"{identity!r}; nothing was sent and nothing was pasted"
        ),
        condition="channel-binding-unproven",
    )
    return None, True


def _by_paste(*, request: DeliveryRequest) -> DeliveryOutcome:
    submitted, effect_unknown = _supervisor_launch.submit_prompt_outcome(
        sup=request.sup,
        target=request.target,
        text=request.text,
        expect_codex=request.is_codex,
    )
    return DeliveryOutcome(
        submitted=submitted,
        effect_unknown=effect_unknown,
        record=_supervisor_channel.DeliveryRecord(
            message=request.kind,
            paste_outcome=paste_outcome(submitted=submitted, effect_unknown=effect_unknown),
        ),
    )


def deliver(
    *, request: DeliveryRequest, channel: _supervisor_channel.MessageChannel | None
) -> DeliveryOutcome:
    """Deliver the owed message through its bound channel, else by the guarded paste.

    ``channel`` is whatever :func:`resolve_bound_channel` proved for this act, so by
    the time delivery runs the binding question is already answered: a runtime with
    no supported channel pastes exactly as it did before this contract existed.
    """
    if channel is None:
        return _by_paste(request=request)
    sent = channel.send(text=request.text)
    # An UNCONFIRMED send is the channel's word for the may-have-landed state a paste
    # reports as an unknown effect, so it rides the SAME flag: the caller's round stays
    # open with its stamp unchanged, exactly as v059 already requires for a paste.
    return DeliveryOutcome(
        submitted=sent.outcome == _supervisor_channel.CHANNEL_DELIVERED,
        effect_unknown=sent.outcome == _supervisor_channel.CHANNEL_UNCONFIRMED,
        record=_supervisor_channel.DeliveryRecord(
            message=request.kind,
            channel=channel.name,
            channel_outcome=sent.outcome,
        ),
    )


def live_identity(*, sup: Supervisor, track: registry.Track, is_codex: bool) -> str | None:
    """The identity this daemon can PROVE is in the track's pane right now, or None."""
    return _supervisor_ready.live_session_identity(
        sup=sup,
        session=_supervisor_launch.session_of(sup=sup, track=track),
        topic=track.topic,
        runtime=_runtime_of(is_codex=is_codex),
    )


def record_delivery(
    *, sup: Supervisor, track: registry.Track, record: _supervisor_channel.DeliveryRecord
) -> str:
    """Carry this act's route onto the track's row and return the phrase for the log.

    One string reaches both surfaces, so an operator comparing a row against the log
    is comparing the same fact rather than two renderings of it.
    """
    istate = sup.inject.setdefault(
        track_key(repo=track.repo, topic=track.topic), _supervisor_records.InjectState()
    )
    istate.last_delivery = record
    return _supervisor_channel.delivery_path(record=record)
