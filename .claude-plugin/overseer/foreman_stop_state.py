"""Machine-readable foreman loop stop and hold state."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import jsonio
from foreman_runtime_state import atomic_json

__all__: list[str] = [
    "FOREMAN_STOP_COMPLETED",
    "FOREMAN_STOP_DIED",
    "FOREMAN_STOP_HELD",
    "ForemanStopState",
    "clear_foreman_stop_state",
    "foreman_hold_path",
    "foreman_stop_path",
    "read_foreman_stop_state",
    "record_completed_bounded_run",
    "record_runtime_stop_state",
    "record_tick_deadline_lapsed",
    "write_foreman_heartbeat",
]

FOREMAN_STOP_DIED = "died"
FOREMAN_STOP_HELD = "held"
FOREMAN_STOP_COMPLETED = "completed-bounded-run"
_FOREMAN_DIR = "foreman"
_STOP_FILE = "stop.json"
_HOLD_FILE = "HOLD.md"
_HEARTBEAT_FILE = "heartbeat.json"


@dataclass(frozen=True, kw_only=True)
class ForemanStopState:
    state: str
    reason: str
    observed_at: str | None
    lapsed_at: str | None = None


class ForemanHeartbeatLapse(Protocol):
    @property
    def stale(self) -> bool: ...

    @property
    def heartbeat_written_at(self) -> datetime: ...

    @property
    def stale_after_seconds(self) -> float: ...


def foreman_stop_path(*, repo: str | Path) -> Path:
    return Path(repo) / "tmp" / "overseer" / _FOREMAN_DIR / _STOP_FILE


def foreman_hold_path(*, repo: str | Path) -> Path:
    return Path(repo) / "tmp" / "overseer" / _FOREMAN_DIR / _HOLD_FILE


def clear_foreman_stop_state(*, repo: str | Path) -> None:
    foreman_stop_path(repo=repo).unlink(missing_ok=True)


def _heartbeat_path(*, repo: str | Path) -> Path:
    return Path(repo) / "tmp" / "overseer" / _FOREMAN_DIR / _HEARTBEAT_FILE


def _timestamp(*, epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text_summary(*, path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            cleaned = stripped.strip()
            if cleaned:
                return cleaned
    except OSError:
        return "operator hold"
    return "operator hold"


def _read_json_stop(*, repo: str | Path) -> ForemanStopState | None:
    try:
        parsed = jsonio.parse_object(text=foreman_stop_path(repo=repo).read_text(encoding="utf-8"))
        if jsonio.is_parse_failure(result=parsed):
            return None
        payload = parsed.unwrap()
        if payload is None:
            return None
        state = payload.get("state")
        reason = payload.get("reason")
        observed_at = payload.get("observed_at")
        lapsed_at = payload.get("lapsed_at")
    except (OSError, AttributeError):
        return None
    if (
        state in {FOREMAN_STOP_DIED, FOREMAN_STOP_COMPLETED}
        and isinstance(reason, str)
        and isinstance(observed_at, str)
        and (lapsed_at is None or isinstance(lapsed_at, str))
    ):
        return ForemanStopState(
            state=state,
            reason=reason,
            observed_at=observed_at,
            lapsed_at=lapsed_at,
        )
    return None


def read_foreman_stop_state(*, repo: str | Path) -> ForemanStopState | None:
    hold = foreman_hold_path(repo=repo)
    if hold.is_file():
        return ForemanStopState(
            state=FOREMAN_STOP_HELD,
            reason=_text_summary(path=hold),
            observed_at=None,
        )
    return _read_json_stop(repo=repo)


def _write_stop(
    *,
    repo: str | Path,
    state: str,
    reason: str,
    observed_at: str,
    lapsed_at: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "state": state,
        "reason": reason,
        "observed_at": observed_at,
    }
    if lapsed_at is not None:
        payload["lapsed_at"] = lapsed_at
    atomic_json(path=foreman_stop_path(repo=repo), payload=payload)


def record_tick_deadline_lapsed(
    *,
    repo: str | Path,
    heartbeat_written_at: datetime,
    stale_after_seconds: float,
    now: Callable[[], float],
) -> None:
    _write_stop(
        repo=repo,
        state=FOREMAN_STOP_DIED,
        reason="tick-deadline-lapsed",
        observed_at=_timestamp(epoch_seconds=now()),
        lapsed_at=_timestamp(epoch_seconds=heartbeat_written_at.timestamp() + stale_after_seconds),
    )


def record_completed_bounded_run(
    *, repo: str | Path, reason: str, now: Callable[[], float]
) -> None:
    _write_stop(
        repo=repo,
        state=FOREMAN_STOP_COMPLETED,
        reason=reason,
        observed_at=_timestamp(epoch_seconds=now()),
    )


def record_runtime_stop_state(
    *,
    repo: str | Path,
    lapse: ForemanHeartbeatLapse | None,
    exit_reason: str | None,
    auto_resume_interval_seconds: float | None,
    now: Callable[[], float],
) -> None:
    if lapse is not None and lapse.stale:
        record_tick_deadline_lapsed(
            repo=repo,
            heartbeat_written_at=lapse.heartbeat_written_at,
            stale_after_seconds=lapse.stale_after_seconds,
            now=now,
        )
        return
    if exit_reason is not None and auto_resume_interval_seconds is None:
        record_completed_bounded_run(repo=repo, reason=exit_reason, now=now)


def write_foreman_heartbeat(
    *,
    repo: str | Path,
    tick_generation: int,
    interval_seconds: float,
    now: Callable[[], float],
) -> None:
    atomic_json(
        path=_heartbeat_path(repo=repo),
        payload={
            "written_at": _timestamp(epoch_seconds=now()),
            "pid": os.getpid(),
            "tick_generation": tick_generation,
            "tick_interval_seconds": interval_seconds,
        },
    )
