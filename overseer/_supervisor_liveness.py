"""Liveness helper primitives for duration, alert identity, and row notes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_config import (
    BLOCKED_AGE_ALERT_BANDS,
    SUPERVISION_CONDITIONS,
    track_key,
)
from _supervisor_records import InjectState
from _supervisor_view import MAX_REASON_IN_ALERT, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "BlockedAlertRequest",
    "age_label",
    "append_note",
    "blocked_age",
    "blocked_band_seconds",
    "clear_alert_conditions",
    "surface_blocked_alerts",
    "threshold_for",
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


_SECONDS_PER_HOUR = 3600.0
_SECONDS_PER_DAY = 24 * 3600


def age_label(*, seconds: float) -> str:
    """Compact non-negative age for row notes and quantized alert lines."""
    clamped = max(0.0, seconds)
    if clamped < _SECONDS_PER_HOUR:
        return f"{int(clamped // 60)}m"
    return f"{int(clamped // _SECONDS_PER_HOUR)}h"


def blocked_age(*, sup: Supervisor, declared: signals.TrackState | None) -> float | None:
    """Age of a blocked declaration, clamped against clock skew."""
    if declared is None or declared.token != signals.STATE_BLOCKED:
        return None
    return max(0.0, sup.now() - declared.mtime)


def blocked_band_seconds(*, age: float) -> list[int]:
    """Blocked alert bands crossed by AGE, including the daily cadence after 24h."""
    bands = [int(band) for band in BLOCKED_AGE_ALERT_BANDS if age >= band]
    next_daily = 2 * _SECONDS_PER_DAY
    while age >= next_daily:
        bands.append(next_daily)
        next_daily += _SECONDS_PER_DAY
    return bands


def append_note(*, note: str | None, extra: str | None) -> str | None:
    if extra is None:
        return note
    if note is None:
        return extra
    return f"{note}; {extra}"


def clear_alert_conditions(
    *, sup: Supervisor, repo: str, topic: str, conditions: frozenset[str]
) -> None:
    """Drop alert keys whose own condition is no longer active for this track."""
    prefix = track_key(repo=repo, topic=topic)
    sup.alerted = {
        key: value
        for key, value in sup.alerted.items()
        if key[:2] != prefix or key[2] in SUPERVISION_CONDITIONS or key[2] in conditions
    }


def threshold_for(*, sup: Supervisor, track: registry.Track) -> int:
    """Track override if present, otherwise the daemon-wide warn threshold."""
    return track.ctx_threshold if track.ctx_threshold is not None else sup.warn_percent


def surface_blocked_alerts(*, request: BlockedAlertRequest) -> set[str]:
    """Emit entry and crossed-band blocked alerts; return active condition keys."""
    active_conditions = {"blocked-human"}
    sup, track, istate = request.sup, request.track, request.istate
    repo, topic = track.repo, track.topic
    if request.declaration_mtime is None:
        istate.blocked_declaration_mtime = None
        istate.blocked_entry_age_label = None
        istate.blocked_alerted_bands = set()
    elif istate.blocked_declaration_mtime != request.declaration_mtime:
        clear_alert_conditions(sup=sup, repo=repo, topic=topic, conditions=frozenset())
        istate.blocked_declaration_mtime = request.declaration_mtime
        istate.blocked_entry_age_label = request.blocked_age_label
        istate.blocked_alerted_bands = set(blocked_band_seconds(age=request.blocked_age or 0.0))
    for band in sorted(istate.blocked_alerted_bands):
        active_conditions.add(f"blocked-age-{band}")

    alert_age = istate.blocked_entry_age_label or request.blocked_age_label or "0m"
    sup.alert(
        repo=repo,
        topic=topic,
        session=request.session,
        pane=request.pane,
        message=(
            f"blocked on human ({alert_age}): "
            f"{elide(text=request.detail, limit=MAX_REASON_IN_ALERT)} "
            "— answer it IN THAT PANE"
        ),
        condition="blocked-human",
    )
    if request.blocked_age is None:
        return active_conditions
    for band in blocked_band_seconds(age=request.blocked_age):
        if band in istate.blocked_alerted_bands:
            continue
        istate.blocked_alerted_bands.add(band)
        active_conditions.add(f"blocked-age-{band}")
        sup.alert(
            repo=repo,
            topic=topic,
            session=request.session,
            pane=request.pane,
            message=(
                f"blocked on human ({age_label(seconds=band)}): "
                f"{elide(text=request.detail, limit=MAX_REASON_IN_ALERT)} "
                "— answer it IN THAT PANE"
            ),
            condition=f"blocked-age-{band}",
        )
    return active_conditions
