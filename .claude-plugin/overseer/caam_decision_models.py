"""Data models for the pure caam account-rotation decision core."""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = [
    "ActiveAccount",
    "EligibleProfiles",
    "ExtraUsage",
    "ProfileUsage",
    "UsageRecord",
    "WindowDollars",
]


@dataclass(frozen=True, kw_only=True)
class WindowDollars:
    """What one usage window reports in DOLLARS, for a plan that reports dollars.

    Carried BESIDE the percentages the same window reports, never instead of
    them: all three figures are null on a Max subscription, which is the whole
    fleet this operation manages, so every quota figure it compares is still a
    percentage. They are read anyway because the response carries them and
    discarding a reading is how the dollar dimension went unnoticed in the first
    place.
    """

    limit: float | None
    used: float | None
    remaining: float | None


@dataclass(frozen=True, kw_only=True)
class ExtraUsage:
    """The pay-as-you-go DOLLAR meter that rides on an account beside its included quota.

    A SEPARATE meter from the utilization percentages, and the reason an account
    can read healthy on every one of them while it is already spending money:
    dollars are only spent once an included allowance is gone, and the meter that
    records them is not the meter the percentages come from.

    `spend_limit_reached` is the fact selection turns on. An account that has hit
    its monthly dollar cap has exhausted its included quota AND the paid path
    that was standing in for it, so there is nothing left for it to serve a
    request from.
    """

    is_enabled: bool
    spend_limit_reached: bool
    monthly_limit: float | None
    used_credits: float | None


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

    The three dollar fields default to None, and that default is load-bearing
    rather than a convenience: it is what a record built from anything other than
    a fresh poll -- a remembered snapshot, a test scenario written before the
    meter existed -- carries, and every predicate reads it as "no meter was
    read", never as "the meter read zero" and never as spending. An account whose
    dollar meter was never observed is therefore treated exactly as it was before
    the meter was read at all.
    """

    five_hour_remaining: float
    seven_day_remaining: float
    five_hour_resets_at: str | None
    seven_day_resets_at: str | None
    fable_remaining: float | None
    fable_resets_at: str | None
    extra_usage: ExtraUsage | None = None
    five_hour_dollars: WindowDollars | None = None
    seven_day_dollars: WindowDollars | None = None


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
