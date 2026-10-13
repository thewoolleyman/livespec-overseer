"""Selection and reporting for the lowest-precedence expiring-quota drain."""

from __future__ import annotations

from datetime import datetime, timezone
from math import inf
from typing import Final, cast

from caam_decision import ActiveAccount, ProfileUsage, UsageRecord, rank_profiles, resets_at
from caam_rendering import until

__all__: list[str] = [
    "DRAIN_TRIGGER",
    "drain_switch_line",
    "drain_target",
    "drain_trigger_line",
]

DRAIN_TRIGGER: Final = "expiring-weekly-quota"
_RESET_TOLERANCE_S: Final = 60.0


def drain_target(
    *,
    profiles: tuple[ProfileUsage, ...],
    active: ActiveAccount,
) -> ProfileUsage | None:
    """The soonest-resetting account whose weekly reset precedes the active one."""
    active_reset = resets_at(timestamp=active.usage.seven_day_resets_at)
    if active_reset == inf:
        return None
    candidates = tuple(
        profile
        for profile in profiles
        if profile.name != active.name
        and profile.usage is not None
        and resets_at(timestamp=profile.usage.seven_day_resets_at)
        <= active_reset - _RESET_TOLERANCE_S
    )
    ranked = rank_profiles(profiles=candidates, scoped_pin=active.scoped_pin)
    return None if not ranked else ranked[0]


def drain_trigger_line(*, target: ProfileUsage, now: float) -> str:
    usage = cast(UsageRecord, target.usage)
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    return (
        "trigger: expiring weekly quota -- "
        f"{target.name} has {usage.seven_day_remaining:.0f}% week left resetting in "
        f"{until(timestamp=usage.seven_day_resets_at, now=now_dt)}"
    )


def drain_switch_line(*, active_name: str, target: ProfileUsage, now: float) -> str:
    usage = cast(UsageRecord, target.usage)
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    return (
        f"SWITCHED {active_name} -> {target.name} "
        "(expiring weekly quota; target has "
        f"{usage.seven_day_remaining:.0f}% week left, resets in "
        f"{until(timestamp=usage.seven_day_resets_at, now=now_dt)})"
    )
