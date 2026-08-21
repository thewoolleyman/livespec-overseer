"""Pure decision helpers for caam account rotation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from math import inf

from caam_rendering import (
    SwitchTargetSummary,
    current_cell,
    decision_dry_run,
    decision_forced,
    decision_hold_allowance,
    decision_hold_no_candidate,
    decision_switched,
    decision_trigger,
    fmt_duration,
    render_table,
    trigger_header,
    until,
)

__all__: list[str] = [
    "EligibleProfiles",
    "ProfileUsage",
    "SwitchTargetSummary",
    "UsageRecord",
    "binding",
    "current_cell",
    "decision_dry_run",
    "decision_forced",
    "decision_hold_allowance",
    "decision_hold_no_candidate",
    "decision_switched",
    "decision_trigger",
    "eligible_profiles",
    "fmt_duration",
    "is_eligible",
    "rank_profiles",
    "render_table",
    "resets_at",
    "trigger_header",
    "triggered",
    "until",
    "weekly_left",
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


_FULLY_SPENT = 100.0


def weekly_left(*, usage: UsageRecord) -> float:
    return 100.0 - usage.seven_day


def binding(*, usage: UsageRecord) -> tuple[str, float, str]:
    if usage.five_hour >= five_hour_threshold():
        return ("five_hour", usage.five_hour, "5-hour window")
    if weekly_left(usage=usage) < weekly_reserve():
        return ("seven_day", usage.seven_day, "weekly reserve")
    return ("five_hour", usage.five_hour, "5-hour window")


def triggered(*, usage: UsageRecord) -> bool:
    return usage.five_hour >= five_hour_threshold() or weekly_left(usage=usage) < weekly_reserve()


def is_eligible(
    *, usage: UsageRecord | None, current: UsageRecord, gain_needed: float, dimension: str
) -> bool:
    return (
        usage is not None
        and dimension in {"five_hour", "seven_day"}
        and dimension_spent(usage=current, dimension=dimension)
        - dimension_spent(usage=usage, dimension=dimension)
        >= gain_needed
        and usage.seven_day < _FULLY_SPENT
        and usage.five_hour < _FULLY_SPENT
    )


def eligible_profiles(
    *,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    current: UsageRecord,
    force: bool,
    dimension: str,
) -> EligibleProfiles:
    gain_needed = 0.01 if force else float(os.environ.get("CAAM_ROTATE_MIN_HEADROOM_GAIN", "10"))
    eligible = tuple(
        profile
        for profile in profiles
        if candidate_allowed(
            profile=profile,
            active_name=active_name,
            current=current,
            gain_needed=gain_needed,
            dimension=dimension,
            enforce_reserve=True,
        )
    )
    if eligible or not every_live_account_under_reserve(profiles=profiles):
        return EligibleProfiles(profiles=eligible, reserve_released=False, note=None)

    released = tuple(
        profile
        for profile in profiles
        if candidate_allowed(
            profile=profile,
            active_name=active_name,
            current=current,
            gain_needed=gain_needed,
            dimension=dimension,
            enforce_reserve=False,
        )
    )
    reserve = weekly_reserve()
    note = f"note: every account is under the {reserve:g}% weekly reserve -- releasing it"
    return EligibleProfiles(profiles=released, reserve_released=bool(released), note=note)


def rank_profiles(*, profiles: tuple[ProfileUsage, ...]) -> tuple[ProfileUsage, ...]:
    return tuple(
        sorted(
            profiles,
            key=lambda profile: resets_at(
                timestamp=None if profile.usage is None else profile.usage.seven_day_resets_at
            ),
        )
    )


def resets_at(*, timestamp: str | None) -> float:
    if not timestamp:
        return inf
    normalized = timestamp.removesuffix("Z") + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return inf
    return parsed.timestamp()


def five_hour_threshold() -> float:
    return float(os.environ.get("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "85"))


def weekly_reserve() -> float:
    return float(os.environ.get("CAAM_ROTATE_WEEKLY_RESERVE", "10"))


def dimension_spent(*, usage: UsageRecord, dimension: str) -> float:
    return {"five_hour": usage.five_hour, "seven_day": usage.seven_day}.get(dimension, inf)


def candidate_allowed(
    *,
    profile: ProfileUsage,
    active_name: str,
    current: UsageRecord,
    gain_needed: float,
    dimension: str,
    enforce_reserve: bool,
) -> bool:
    return (
        profile.name != active_name
        and profile.source == "live"
        and profile.usage is not None
        and (not enforce_reserve or weekly_left(usage=profile.usage) >= weekly_reserve())
        and is_eligible(
            usage=profile.usage,
            current=current,
            gain_needed=gain_needed,
            dimension=dimension,
        )
    )


def every_live_account_under_reserve(*, profiles: tuple[ProfileUsage, ...]) -> bool:
    live_usages = tuple(profile.usage for profile in profiles if profile.source == "live")
    return bool(live_usages) and all(
        usage is not None and weekly_left(usage=usage) < weekly_reserve() for usage in live_usages
    )
