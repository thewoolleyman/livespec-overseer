"""Liveness helper primitives for duration, alert identity, and row notes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
from _supervisor_liveness_time import (
    age_label,
    age_label_or_none,
    append_note,
    blocked_age,
    blocked_band_seconds,
    blocked_note,
    clear_alert_conditions,
    threshold_for,
)
from _supervisor_ready_alerts import uncertifiable_ready_surface
from _supervisor_records import InjectState
from _supervisor_view import MAX_REASON_IN_ALERT, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "BlockedAlertRequest",
    "age_label",
    "age_label_or_none",
    "append_note",
    "blocked_age",
    "blocked_band_seconds",
    "blocked_note",
    "clear_alert_conditions",
    "surface_blocked_alerts",
    "surface_picker_stall_alert",
    "threshold_for",
    "uncertifiable_ready_surface",
]


@dataclass(frozen=True, kw_only=True)
class BlockedAlertRequest:
    sup: Supervisor
    track: registry.Track
    session: str
    pane: str
    detail: str
    declaration_mtime: float | None
    blocked_age: float | None
    blocked_age_label: str | None
    istate: InjectState


def surface_blocked_alerts(*, request: BlockedAlertRequest) -> set[str]:
    """Emit entry and crossed-band blocked alerts; return active condition keys."""
    active_conditions = {"blocked-human"}
    sup, track, istate = request.sup, request.track, request.istate
    repo, topic = track.repo, track.topic
    crossed = blocked_band_seconds(age=request.blocked_age or 0.0)
    if request.declaration_mtime is None:
        istate.blocked_declaration_mtime = None
        istate.blocked_entry_age_label = None
        istate.blocked_alerted_bands = set()
    elif istate.blocked_declaration_mtime != request.declaration_mtime:
        clear_alert_conditions(sup=sup, repo=repo, topic=topic, conditions=frozenset())
        istate.blocked_declaration_mtime = request.declaration_mtime
        istate.blocked_alerted_bands = set(crossed)
        if crossed:
            istate.blocked_entry_age_label = age_label(seconds=max(crossed))
            active_conditions.update(f"blocked-age-{item}" for item in crossed)
        else:
            istate.blocked_entry_age_label = request.blocked_age_label
    for band in sorted(istate.blocked_alerted_bands):
        active_conditions.add(f"blocked-age-{band}")

    alert_age = istate.blocked_entry_age_label or request.blocked_age_label or "0m"
    _alert_blocked(request=request, age=alert_age, condition="blocked-human")
    if request.blocked_age is None:
        return active_conditions
    for band in crossed:
        if band in istate.blocked_alerted_bands:
            continue
        istate.blocked_alerted_bands.add(band)
        active_conditions.add(f"blocked-age-{band}")
        _alert_blocked(
            request=request,
            age=age_label(seconds=band),
            condition=f"blocked-age-{band}",
        )
    return active_conditions


def surface_picker_stall_alert(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    stall_seconds: int,
) -> set[str]:
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=(
            f"picker stalled ({age_label(seconds=stall_seconds)}): "
            "structured picker has not changed — unblock it IN THAT PANE"
        ),
        condition="picker-stalled",
    )
    return {"picker-stalled"}


def _alert_blocked(*, request: BlockedAlertRequest, age: str, condition: str) -> None:
    request.sup.alert(
        repo=request.track.repo,
        topic=request.track.topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"blocked on human ({age}): "
            f"{elide(text=request.detail, limit=MAX_REASON_IN_ALERT)} "
            "— answer it IN THAT PANE"
        ),
        condition=condition,
    )
