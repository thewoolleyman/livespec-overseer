"""Shared liveness duration, note, and condition primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_config import (
    BLOCKED_AGE_ALERT_BANDS,
    SUPERVISION_CONDITIONS,
    track_key,
)

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "age_label",
    "age_label_or_none",
    "append_note",
    "blocked_age",
    "blocked_band_seconds",
    "blocked_note",
    "clear_alert_conditions",
    "threshold_for",
]

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
