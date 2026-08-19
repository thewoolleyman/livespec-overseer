"""Report-only attention for cross-session delivery parked behind a picker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_liveness
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "PARKED_DELIVERY_STATUS",
    "ParkedDeliveryDecision",
    "ParkedDeliveryRequest",
    "apply_parked_delivery_attention",
]

PARKED_DELIVERY_STATUS = "parked-delivery"


@dataclass(frozen=True, kw_only=True)
class ParkedDeliveryDecision:
    status: str
    note: str | None
    active_conditions: set[str]


@dataclass(frozen=True, kw_only=True)
class ParkedDeliveryRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    status: str
    note: str | None
    obs: Observation
    active_conditions: set[str]
    act: bool


def apply_parked_delivery_attention(*, request: ParkedDeliveryRequest) -> ParkedDeliveryDecision:
    if not request.obs.gate:
        return _unchanged(request=request)
    sender = signals.queued_cross_session_delivery_sender(capture_text=request.obs.capture)
    if sender is None:
        return _unchanged(request=request)

    note = _supervisor_liveness.append_note(
        note=request.note, extra=f"queued delivery from {sender}"
    )
    active_conditions = {*request.active_conditions, PARKED_DELIVERY_STATUS}
    if request.act:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                f"queued delivery from {sender} is parked behind an open picker "
                "- inspect that pane; report-only, no restart authorized"
            ),
            condition=PARKED_DELIVERY_STATUS,
        )
    return ParkedDeliveryDecision(
        status=PARKED_DELIVERY_STATUS,
        note=note,
        active_conditions=active_conditions,
    )


def _unchanged(*, request: ParkedDeliveryRequest) -> ParkedDeliveryDecision:
    return ParkedDeliveryDecision(
        status=request.status,
        note=request.note,
        active_conditions=set(request.active_conditions),
    )
