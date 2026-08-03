"""PID plus /proc start-time singleton lock for the foreman runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _seams import PidToOptionalStr
from foreman_runtime_state import atomic_json, read_json_object

__all__: list[str] = ["ForemanLock", "LockResult"]


@dataclass(frozen=True, kw_only=True)
class LockResult:
    acquired: bool
    reason: str


class ForemanLock:
    def __init__(self, *, path: Path) -> None:
        self.path = path

    def acquire(self, *, pid: int, start_time: str, start_time_of: PidToOptionalStr) -> LockResult:
        existing = read_json_object(path=self.path)
        old_pid = existing.get("pid")
        old_start = existing.get("start_time")
        if isinstance(old_pid, int) and isinstance(old_start, str):
            live_start = start_time_of(pid=old_pid)
            if live_start == old_start:
                return LockResult(
                    acquired=False,
                    reason=f"held by live pid {old_pid} with matching /proc start-time",
                )
        atomic_json(path=self.path, payload={"pid": pid, "start_time": start_time})
        return LockResult(acquired=True, reason="acquired")
