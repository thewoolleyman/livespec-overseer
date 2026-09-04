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
    """What each of an account's allowances has LEFT, as a percentage.

    The field names carry the direction, which is the whole point of them: a
    field called `five_hour` said nothing about which way its number ran, so
    every reader had to trace it back to the response it was parsed from. The
    figures are still DERIVED from the usage response's utilization percentages,
    exactly as the specification requires; the complement happens once, at the
    parse boundary that is named for doing it (`caam_usage`), and the two
    directions never travel together past that point.

    `fable_remaining` is None for an account whose scoped-model allowance could
    not be read at all, which is a different fact from zero remaining and is
    kept distinct: every predicate downstream fails closed on the None.
    """

    five_hour_remaining: float
    seven_day_remaining: float
    five_hour_resets_at: str | None
    seven_day_resets_at: str | None
    fable_remaining: float | None
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
