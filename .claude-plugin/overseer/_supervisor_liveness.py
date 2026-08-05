"""Liveness helper primitives for duration, alert identity, and row notes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_config import (
    BLOCKED_AGE_ALERT_BANDS,
    CONDITION_CONTINUITY_GAP,
    SUPERVISION_CONDITIONS,
    track_key,
)
from _supervisor_records import InjectState, Observation
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


_SECONDS_PER_HOUR = 3600.0
_SECONDS_PER_DAY = 24 * 3600


def age_label(*, seconds: float) -> str:
    """Compact non-negative age for row notes and quantized alert lines."""
    clamped = max(0.0, seconds)
    if clamped < _SECONDS_PER_HOUR:
        return f"{int(clamped // 60)}m"
    return f"{int(clamped // _SECONDS_PER_HOUR)}h"


def age_label_or_none(*, seconds: float | None) -> str | None:
    """Compact age label, preserving ``None`` for absent declaration ages."""
    return age_label(seconds=seconds) if seconds is not None else None


def blocked_age(*, sup: Supervisor, declared: signals.TrackState | None) -> float | None:
    """Age of a blocked declaration, clamped against clock skew."""
    if declared is None or declared.token != signals.STATE_BLOCKED:
        return None
    return max(0.0, sup.now() - declared.mtime)


def blocked_note(*, blocked: str | None, blocked_age_label: str | None) -> str | None:
    """Row note for a blocked declaration, carrying its duration when known."""
    if blocked is None:
        return None
    if blocked_age_label is None:
        return blocked
    return f"{blocked_age_label}: {blocked}"


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


def reset_uncertifiable_ready_state(*, istate: InjectState) -> None:
    istate.uncertifiable_ready_mtime = None
    istate.uncertifiable_ready_entry_age_label = None
    istate.uncertifiable_ready_alerted_bands = set()


def uncertifiable_ready_surface(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    obs: Observation,
    act: bool,
) -> tuple[str, set[str]] | None:
    """Return the report-only surface for a `ready` that cannot certify, if due."""
    declared = obs.declared
    if declared is None or declared.token != signals.STATE_READY:
        reset_uncertifiable_ready_state(istate=obs.istate)
        return None
    if obs.ready_uncertifiable_reason is None:
        reset_uncertifiable_ready_state(istate=obs.istate)
        return None
    reason = obs.ready_uncertifiable_reason

    istate = obs.istate
    age = max(0.0, sup.now() - declared.mtime)
    if age < CONDITION_CONTINUITY_GAP:
        return None

    active_conditions = {"ready-uncertifiable"}
    note = f"{age_label(seconds=age)}: ready cannot certify: {reason}"
    if not act:
        return note, active_conditions

    if istate.uncertifiable_ready_mtime != declared.mtime:
        clear_alert_conditions(sup=sup, repo=track.repo, topic=track.topic, conditions=frozenset())
        istate.uncertifiable_ready_mtime = declared.mtime
        istate.uncertifiable_ready_entry_age_label = age_label(seconds=age)
        istate.uncertifiable_ready_alerted_bands = set(blocked_band_seconds(age=age))
    for band in blocked_band_seconds(age=age):
        active_conditions.add(f"ready-uncertifiable-age-{band}")

    alert_age = istate.uncertifiable_ready_entry_age_label or age_label(seconds=age)
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=(
            f"ready cannot certify ({alert_age}): {reason} — "
            "clear the state file or resolve it in that pane"
        ),
        condition="ready-uncertifiable",
    )
    new_bands = [
        band
        for band in blocked_band_seconds(age=age)
        if band not in istate.uncertifiable_ready_alerted_bands
    ]
    istate.uncertifiable_ready_alerted_bands.update(new_bands)
    for band in new_bands:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=pane,
            message=(
                f"ready cannot certify ({age_label(seconds=band)}): {reason} — "
                "clear the state file or resolve it in that pane"
            ),
            condition=f"ready-uncertifiable-age-{band}",
        )
    return note, active_conditions


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
