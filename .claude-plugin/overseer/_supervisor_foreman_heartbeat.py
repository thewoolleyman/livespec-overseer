"""Shared foreman heartbeat parsing and cadence freshness policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import jsonio

__all__: list[str] = [
    "FOREMAN_TOPIC",
    "Heartbeat",
    "HeartbeatLapse",
    "foreman_heartbeat_fresh",
    "heartbeat_lapse",
    "heartbeat_path",
    "read_heartbeat",
    "stale_after",
]

FOREMAN_TOPIC = "foreman"
_HEARTBEAT_FILE = "heartbeat.json"
_STALE_FLOOR_SECONDS = 30.0 * 60.0
_STALE_MULTIPLIER = 2.0


@dataclass(frozen=True, kw_only=True)
class Heartbeat:
    written_at: datetime
    pid: int
    tick_generation: int
    tick_interval_seconds: float


@dataclass(frozen=True, kw_only=True)
class HeartbeatLapse:
    age_seconds: float
    stale: bool
    heartbeat_written_at: datetime
    stale_after_seconds: float


def heartbeat_path(*, repo: str) -> Path:
    return Path(repo) / "tmp" / "overseer" / FOREMAN_TOPIC / _HEARTBEAT_FILE


def _as_non_bool_int(*, value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _parse_timestamp(*, value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_heartbeat(*, repo: str) -> Heartbeat | None:
    """Read a foreman heartbeat, treating unreadable or malformed content as absent.

    Fail-closed includes valid JSON with the wrong shape or wrong field types. A torn
    write can leave an array, scalar, numeric timestamp, or list-valued interval, and
    none of those may escape into the daemon tick.
    """
    try:
        parsed = jsonio.parse_object(text=heartbeat_path(repo=repo).read_text(encoding="utf-8"))
        if jsonio.is_parse_failure(result=parsed):
            return None
        payload = parsed.unwrap()
        if payload is None:
            return None
        written_raw = payload["written_at"]
        if not isinstance(written_raw, str):
            return None
        written_at = _parse_timestamp(value=written_raw)
        pid = _as_non_bool_int(value=payload["pid"])
        tick_generation = _as_non_bool_int(value=payload["tick_generation"])
        tick_interval_seconds = jsonio.as_float(value=payload["tick_interval_seconds"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if (
        pid is not None
        and tick_generation is not None
        and tick_interval_seconds is not None
        and tick_interval_seconds > 0
    ):
        return Heartbeat(
            written_at=written_at,
            pid=pid,
            tick_generation=tick_generation,
            tick_interval_seconds=tick_interval_seconds,
        )
    return None


def _age_seconds(*, heartbeat: Heartbeat, now: Callable[[], float]) -> float:
    return now() - heartbeat.written_at.timestamp()


def stale_after(*, heartbeat: Heartbeat) -> float:
    return max(_STALE_FLOOR_SECONDS, _STALE_MULTIPLIER * heartbeat.tick_interval_seconds)


def heartbeat_lapse(*, repo: str, now: Callable[[], float]) -> HeartbeatLapse | None:
    """Read the PRIOR heartbeat's staleness, before a caller overwrites it.

    A `ForemanRuntime.step()` caller reads this before writing its own heartbeat, so a
    lapsed recurring loop (no tick landed within `2x` its interval, floor 30 minutes)
    is visible to THIS tick immediately, rather than only after the daemon's own poll
    notices it. Returns None when no prior heartbeat exists.
    """
    heartbeat = read_heartbeat(repo=repo)
    if heartbeat is None:
        return None
    age = _age_seconds(heartbeat=heartbeat, now=now)
    stale_after_seconds = stale_after(heartbeat=heartbeat)
    return HeartbeatLapse(
        age_seconds=age,
        stale=age > stale_after_seconds,
        heartbeat_written_at=heartbeat.written_at,
        stale_after_seconds=stale_after_seconds,
    )


def foreman_heartbeat_fresh(*, repo: str, now: Callable[[], float]) -> bool:
    heartbeat = read_heartbeat(repo=repo)
    if heartbeat is None:
        return False
    return _age_seconds(heartbeat=heartbeat, now=now) <= stale_after(heartbeat=heartbeat)
