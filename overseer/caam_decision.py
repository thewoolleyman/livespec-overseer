"""Pure decision helpers for caam account rotation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from math import inf

from caam_decision_models import EligibleProfiles, ProfileUsage, UsageRecord
from caam_decision_protection import (
    NO_PROTECTION_FLOORS,
    CandidatePolicy,
    candidate_allowed,
    dimension_spent,
    empty_release_note,
    is_eligible,
    protection_floor_for,
    raw_weekly_left,
    select_candidate_set,
    weekly_left,
)
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
    "candidate_allowed",
    "current_cell",
    "decision_dry_run",
    "decision_forced",
    "decision_hold_allowance",
    "decision_hold_no_candidate",
    "decision_switched",
    "decision_trigger",
    "dimension_spent",
    "eligible_profiles",
    "five_hour_threshold",
    "fmt_duration",
    "is_eligible",
    "min_headroom_gain",
    "rank_profiles",
    "render_table",
    "resets_at",
    "trigger_header",
    "triggered",
    "until",
    "weekly_left",
    "weekly_reserve",
]


def binding(
    *,
    usage: UsageRecord,
    active_name: str | None = None,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
) -> tuple[str, float, str]:
    protection_floor = protection_floor_for(name=active_name, protection_floors=protection_floors)
    if usage.five_hour >= five_hour_threshold():
        return ("five_hour", usage.five_hour, "5-hour window")
    if protection_floor > 0 and raw_weekly_left(usage=usage) <= protection_floor:
        return (
            "seven_day",
            usage.seven_day,
            f"protection floor for {active_name} ({protection_floor:g}%)",
        )
    if weekly_left(usage=usage) < weekly_reserve():
        return ("seven_day", usage.seven_day, "weekly reserve")
    return ("five_hour", usage.five_hour, "5-hour window")


def triggered(
    *,
    usage: UsageRecord,
    active_name: str | None = None,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
) -> bool:
    protection_floor = protection_floor_for(name=active_name, protection_floors=protection_floors)
    return (
        usage.five_hour >= five_hour_threshold()
        or weekly_left(usage=usage) < weekly_reserve()
        or (protection_floor > 0 and raw_weekly_left(usage=usage) <= protection_floor)
    )


def eligible_profiles(
    *,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    current: UsageRecord,
    force: bool,
    dimension: str,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
) -> EligibleProfiles:
    gain_needed = 0.01 if force else min_headroom_gain()
    reserve = weekly_reserve()
    eligible = select_candidate_set(
        profiles=profiles,
        active_name=active_name,
        policy=CandidatePolicy(
            current=current,
            gain_needed=gain_needed,
            dimension=dimension,
            enforce_reserve=True,
            weekly_reserve=reserve,
        ),
        protection_floors=protection_floors,
    )
    if eligible or not every_live_account_under_reserve(profiles=profiles):
        return EligibleProfiles(profiles=eligible, reserve_released=False, note=None)

    released = select_candidate_set(
        profiles=profiles,
        active_name=active_name,
        policy=CandidatePolicy(
            current=current,
            gain_needed=gain_needed,
            dimension=dimension,
            enforce_reserve=False,
            weekly_reserve=reserve,
        ),
        protection_floors=protection_floors,
    )
    if not released:
        return EligibleProfiles(
            profiles=(),
            reserve_released=False,
            note=empty_release_note(
                profiles=profiles,
                protection_floors=protection_floors,
                weekly_reserve=reserve,
            ),
        )
    note = empty_release_note(
        profiles=profiles,
        protection_floors=protection_floors,
        weekly_reserve=reserve,
    )
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


def min_headroom_gain() -> float:
    return float(os.environ.get("CAAM_ROTATE_MIN_HEADROOM_GAIN", "10"))


def every_live_account_under_reserve(*, profiles: tuple[ProfileUsage, ...]) -> bool:
    live_usages = tuple(profile.usage for profile in profiles if profile.source == "live")
    return bool(live_usages) and all(
        usage is not None and weekly_left(usage=usage) < weekly_reserve() for usage in live_usages
    )
