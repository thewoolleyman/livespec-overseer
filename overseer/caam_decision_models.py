"""Data models for the pure caam account-rotation decision core."""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = [
    "ActiveAccount",
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
    credential_expired: bool = False


@dataclass(frozen=True, kw_only=True)
class ActiveAccount:
    """The account being left, and whether an operator pin depends on its scoped allowance.

    `scoped_pin` carries ONE fact: an operator pin names the scoped model. The
    ratified scoped-model clause gates its whole exception on that pin being in
    effect "AND ONLY THEN", so selection needs the pin alongside the active
    account's own usage in order to ask whether the pin is still satisfiable
    where the fleet currently sits.
    """

    name: str
    usage: UsageRecord
    scoped_pin: bool = False


@dataclass(frozen=True, kw_only=True)
class EligibleProfiles:
    profiles: tuple[ProfileUsage, ...]
    reserve_released: bool
    note: str | None
