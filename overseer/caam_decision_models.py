"""Data models for the pure caam account-rotation decision core."""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = [
    "EligibleProfiles",
    "ProfileUsage",
    "UsageRecord",
]


@dataclass(frozen=True, kw_only=True)
class UsageRecord:
    five_hour: float
    seven_day: float
    five_hour_resets_at: str | None
    seven_day_resets_at: str | None
    fable: float | None
    fable_resets_at: str | None


@dataclass(frozen=True, kw_only=True)
class ProfileUsage:
    name: str
    source: str
    usage: UsageRecord | None


@dataclass(frozen=True, kw_only=True)
class EligibleProfiles:
    profiles: tuple[ProfileUsage, ...]
    reserve_released: bool
    note: str | None
