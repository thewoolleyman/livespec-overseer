"""Retry a daemon-owned unconfirmed wrap-up before composer text reads as settling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_launch
import _supervisor_observe
import _supervisor_wrapup_round
import registry
from _supervisor_config import DANGER_CTX_REMAINING
from _supervisor_records import InjectState, Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "PendingDelivery",
    "PendingWrapupDecision",
    "clear",
    "pending_alert_conditions",
    "record_delivery",
    "remember",
    "retry_decision",
]

_ALERT_AFTER_SECONDS = 10 * 60
_ALERT_CONDITION = "wrapup-pending-composer"


@dataclass(frozen=True, kw_only=True)
class PendingWrapupDecision:
    status: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class PendingDelivery:
    track: registry.Track
    text: str
    submitted: bool
    paste_unconfirmed: bool
    bands: list[int]
    compaction_latched_at: float | None


def clear(*, state: InjectState) -> None:
    """Forget authority to submit a prior daemon paste."""
    state.pending_wrapup_text = None
    state.pending_wrapup_since = None
    state.pending_wrapup_bands = ()
    state.pending_wrapup_compaction_latched_at = None


def remember(
    *,
    state: InjectState,
    text: str,
    since: float,
    bands: list[int],
    compaction_latched_at: float | None,
) -> None:
    """Retain only this daemon process's authority to complete one wrap-up submit."""
    state.pending_wrapup_text = text
    state.pending_wrapup_since = since
    state.pending_wrapup_bands = tuple(bands)
    state.pending_wrapup_compaction_latched_at = compaction_latched_at


def record_delivery(
    *,
    sup: Supervisor,
    delivery: PendingDelivery,
) -> None:
    """Keep retry authority only for an unconfirmed daemon paste."""
    state = sup.inject.setdefault((delivery.track.repo, delivery.track.topic), InjectState())
    if delivery.submitted or not delivery.paste_unconfirmed:
        clear(state=state)
        return
    remember(
        state=state,
        text=delivery.text,
        since=sup.now(),
        bands=delivery.bands,
        compaction_latched_at=delivery.compaction_latched_at,
    )


def _round_still_authorizes(*, obs: Observation, state: InjectState) -> bool:
    return (
        obs.round_record.at is not None
        and obs.round_record.session_identity is not None
        and obs.round_record.session_identity == obs.session_identity
        and state.pending_wrapup_text is not None
    )


def _status(*, obs: Observation) -> str:
    return "danger" if obs.eff_ctx is not None and obs.eff_ctx <= DANGER_CTX_REMAINING else "warned"


def pending_alert_conditions(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    session: str,
    target: str,
    act: bool,
) -> set[str]:
    """Raise the pending-composer event for a retained payload, whatever the pane is doing.

    Alerting is not the Enter retry: the retry stays blocked in a busy or gated pane,
    but a daemon payload sitting unsubmitted past ``_ALERT_AFTER_SECONDS`` is owed an
    event regardless, once on entry and re-armed when the payload leaves the composer.
    """
    state = obs.istate
    text = state.pending_wrapup_text
    since = state.pending_wrapup_since
    pending_long_enough = since is not None and sup.now() - since >= _ALERT_AFTER_SECONDS
    if (
        text is None
        or not act
        or not pending_long_enough
        or not _round_still_authorizes(obs=obs, state=state)
        or not _supervisor_launch.retained_prompt_visible(sup=sup, target=target, text=text)
    ):
        return set()
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=target,
        message="its own wrap-up is pending in the composer",
        condition=_ALERT_CONDITION,
    )
    return {_ALERT_CONDITION}


def retry_decision(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    session: str,
    target: str,
    act: bool,
) -> PendingWrapupDecision | None:
    """Retry a retained daemon wrap-up only while every original authority holds."""
    state = obs.istate
    text = state.pending_wrapup_text
    if text is None or not act:
        return None
    if (
        not _round_still_authorizes(obs=obs, state=state)
        or not _supervisor_observe.pane_is_managed(
            sup=sup, target=target, repo=track.repo, topic=track.topic, session=session
        )
        or obs.ready
    ):
        clear(state=state)
        return None
    if not _supervisor_launch.retained_prompt_visible(sup=sup, target=target, text=text):
        clear(state=state)
        # Do not immediately paste a new wrap-up into the freshly-cleared composer.
        # The next tick may re-evaluate the ordinary threshold path, but this tick is
        # the edge that re-arms the pending-composer alert and spends no new input.
        return PendingWrapupDecision(status=_status(obs=obs), active_conditions=set())

    # The over-ten-minutes event is NOT raised here: this call is reached only after the
    # busy/gate cascade declined the track, so `pending_alert_conditions` raises it from
    # the evaluator's prologue instead and this decision carries no conditions.
    # The same two-capture settle every guarded paste takes: an Enter into a composer
    # whose pane is still rendering could submit a half-drawn frame.
    if obs.busy or obs.gate or not _supervisor_launch.pane_settled(sup=sup, target=target):
        return PendingWrapupDecision(status=None, active_conditions=set())

    submitted, _effect_unknown = _supervisor_launch.retry_prompt_enter_once(
        sup=sup, target=target, text=text
    )
    if submitted:
        _supervisor_wrapup_round.mark_delivered(
            sup=sup,
            track=track,
            due=list(state.pending_wrapup_bands),
            eff_ctx=obs.eff_ctx or 0,
            compaction_latched_at=state.pending_wrapup_compaction_latched_at,
            path="wrap-up via retained-composer Enter retry: delivered",
        )
        clear(state=state)
    elif not _supervisor_launch.retained_prompt_visible(sup=sup, target=target, text=text):
        clear(state=state)
        return None
    return PendingWrapupDecision(status=_status(obs=obs), active_conditions=set())
