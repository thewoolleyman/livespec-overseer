"""Deliver the bounded recovery notice for a malformed state declaration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_channel
import _supervisor_channel_delivery
import _supervisor_channel_hold
import _supervisor_launch
import _supervisor_observe
import registry
import signals
from _supervisor_config import track_key
from _supervisor_prompts import rejected_state_notice_message
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["maybe_send_rejected_state_notice"]

_RENOTICE_AFTER = 24 * 60 * 60


def _due(*, sup: Supervisor, track: registry.Track, value: str) -> bool:
    record = registry.read_rejected_state_notice(
        repo=track.repo, topic=track.topic, value=value, stamp_path=sup.stamp_path
    )
    return record is None or (
        not record.renoticed and sup.now() - record.noticed_at >= _RENOTICE_AFTER
    )


def _eligible(*, obs: Observation) -> bool:
    return (
        obs.idle
        and not obs.busy
        and not obs.gate
        and obs.claude_status != "waiting"
        and not obs.blocked
        and not obs.acked
        and not obs.ready
    )


def _fresh_eligible(
    *, sup: Supervisor, track: registry.Track, session: str, target: str, value: str
) -> Observation | None:
    if not _supervisor_launch.pane_settled(sup=sup, target=target):
        return None
    if not _supervisor_observe.pane_is_managed(
        sup=sup, target=target, repo=track.repo, topic=track.topic, session=session
    ):
        return None
    fresh = _supervisor_observe.observe(
        sup=sup,
        track=track,
        session=session,
        target=target,
        key=track_key(repo=track.repo, topic=track.topic),
    )
    if signals.rejected_value(repo=track.repo, topic=track.topic) != value:
        return None
    if fresh.declared is not None and signals.valid_session_token(token=fresh.declared.token):
        return None
    return fresh if _eligible(obs=fresh) else None


def maybe_send_rejected_state_notice(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    session: str,
    target: str,
    act: bool,
) -> None:
    """Deliver a rejected-state notice once, and once more after its 24-hour bound."""
    value = obs.rejected_value
    if (
        not act
        or value is None
        or not _due(sup=sup, track=track, value=value)
        or not _eligible(obs=obs)
    ):
        return
    held = _supervisor_channel_hold.held_delivery(sup=sup, track=track)
    if held is not None:
        _supervisor_channel_hold.surface_hold(sup=sup, track=track, hold=held, pane=target)
        return
    fresh = _fresh_eligible(sup=sup, track=track, session=session, target=target, value=value)
    if fresh is None:
        return
    request = _supervisor_channel_delivery.DeliveryRequest(
        sup=sup,
        track=track,
        target=target,
        text=rejected_state_notice_message(repo=track.repo, topic=track.topic, value=value),
        kind=_supervisor_channel.REJECTED_STATE_NOTICE,
        is_codex=fresh.is_codex,
        rejected_value=value,
        reread=lambda: _fresh_eligible(
            sup=sup, track=track, session=session, target=target, value=value
        )
        is not None,
    )
    channel, cancelled = _supervisor_channel_delivery.resolve_bound_channel(
        request=request,
        identity=_supervisor_channel_delivery.live_identity(
            sup=sup, track=track, is_codex=fresh.is_codex
        ),
    )
    if cancelled:
        return
    delivered = _supervisor_channel_delivery.deliver(request=request, channel=channel)
    path = _supervisor_channel_delivery.record_delivery(
        sup=sup, track=track, record=delivered.record
    )
    if delivered.submitted or delivered.effect_unknown:
        _ = registry.record_rejected_state_notice(
            repo=track.repo,
            topic=track.topic,
            value=value,
            noticed_at=sup.now(),
            stamp_path=sup.stamp_path,
        )
        sup.log(message=f"rejected-state-noticed {track.repo}::{track.topic}: {value!r} ({path})")
        return
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message=f"rejected-state notice FAILED (it did not land); will retry ({path})",
        condition="rejected-state-notice-delivery-failed",
    )
