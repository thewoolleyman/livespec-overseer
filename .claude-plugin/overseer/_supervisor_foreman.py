"""Foreman heartbeat observation for the daemon attention surface.

The foreman is an operator surface, not a tracked worker. Its heartbeat therefore
does not enter the session state machine and never authorizes a daemon act. The
daemon only observes one scratch file per watched repo and, when that PRESENT file is
stale, renders a synthetic report-only row through the same table, NEEDS YOU block,
window badge, and edge-triggered alert machinery every other attention member uses.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import jsonio
import registry
from _supervisor_config import track_key
from _supervisor_view import MAX_REASON_IN_ALERT, RowView, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "FOREMAN_HEARTBEAT_STALE_STATUS",
    "FOREMAN_TOPIC",
    "Heartbeat",
    "foreman_row",
    "foreman_rows",
    "heartbeat_path",
    "read_heartbeat",
]

FOREMAN_TOPIC = "foreman"
FOREMAN_HEARTBEAT_STALE_STATUS = "foreman-heartbeat-stale"
_HEARTBEAT_FILE = "heartbeat.json"
_STALE_FLOOR_SECONDS = 30.0 * 60.0
_STALE_MULTIPLIER = 2.0
_ALERT_CONDITION = "foreman-heartbeat-stale"


@dataclass(frozen=True, kw_only=True)
class Heartbeat:
    written_at: datetime
    pid: int
    tick_generation: int
    tick_interval_seconds: float


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
        payload = jsonio.parse_object(text=heartbeat_path(repo=repo).read_text(encoding="utf-8"))
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
    if pid is None or tick_generation is None or tick_interval_seconds is None:
        return None
    if tick_interval_seconds <= 0:
        return None
    return Heartbeat(
        written_at=written_at,
        pid=pid,
        tick_generation=tick_generation,
        tick_interval_seconds=tick_interval_seconds,
    )


def _age_seconds(*, heartbeat: Heartbeat, now: Callable[[], float]) -> float:
    return now() - heartbeat.written_at.timestamp()


def _stale_after(*, heartbeat: Heartbeat) -> float:
    return max(_STALE_FLOOR_SECONDS, _STALE_MULTIPLIER * heartbeat.tick_interval_seconds)


def _interval_label(*, interval: float) -> str:
    if interval.is_integer():
        return str(int(interval))
    return f"{interval:.3f}".rstrip("0").rstrip(".")


def foreman_row(*, repo: str, now: Callable[[], float]) -> RowView | None:
    heartbeat = read_heartbeat(repo=repo)
    if heartbeat is None:
        return None
    age = _age_seconds(heartbeat=heartbeat, now=now)
    if age <= _stale_after(heartbeat=heartbeat):
        return None
    interval = _interval_label(interval=heartbeat.tick_interval_seconds)
    return RowView(
        topic=FOREMAN_TOPIC,
        repo=repo,
        tmux=f"{registry.repo_slug(repo=repo)}-{FOREMAN_TOPIC}",
        ctx=None,
        status=FOREMAN_HEARTBEAT_STALE_STATUS,
        note=(
            f"foreman heartbeat stale {int(age // 60)}m; pid {heartbeat.pid}; "
            f"tick {heartbeat.tick_generation}; interval {interval}s"
        ),
    )


def _clear_alert(*, sup: Supervisor, repo: str) -> None:
    _ = sup.alerted.pop((*track_key(repo=repo, topic=FOREMAN_TOPIC), _ALERT_CONDITION), None)


def _surface_alert(*, sup: Supervisor, row: RowView) -> None:
    note = elide(text=row.note or "foreman heartbeat stale", limit=MAX_REASON_IN_ALERT)
    sup.alert(
        repo=row.repo,
        topic=row.topic,
        session=row.tmux,
        pane=None,
        message=f"foreman heartbeat stale: {note} — inspect that operator surface",
        condition=_ALERT_CONDITION,
    )


def foreman_rows(*, sup: Supervisor, repos: list[str], act: bool) -> list[RowView]:
    rows: list[RowView] = []
    for repo in repos:
        row = foreman_row(repo=repo, now=sup.now)
        if row is None:
            _clear_alert(sup=sup, repo=repo)
            continue
        rows.append(row)
        if act:
            _surface_alert(sup=sup, row=row)
    return rows
