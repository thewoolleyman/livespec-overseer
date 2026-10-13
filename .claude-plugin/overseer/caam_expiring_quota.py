"""Selection and reporting for the lowest-precedence expiring-quota drain."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from math import inf
from typing import Final, cast

import jsonio
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    five_hour_remaining_floor,
    min_headroom_gain,
    resets_at,
    scoped_reserve,
    weekly_reserve,
)
from caam_decision_protection import is_protected, protection_floor_for
from caam_rendering import until

__all__: list[str] = [
    "DRAIN_TRIGGER",
    "drain_switch_line",
    "drain_target",
    "drain_trigger_line",
    "remember_short_window_departure",
]

DRAIN_TRIGGER: Final = "expiring-weekly-quota"
_RESET_TOLERANCE_S: Final = 60.0
_FULLY_REPLENISHED: Final = 100.0
_SHORT_WINDOW_DEPARTURES: Final = "short_window_departures"


def remember_short_window_departure(
    *, state: dict[str, object], account: str, resets_at_value: str | None
) -> None:
    """Record the short-window reset observed when an account was left."""
    remembered = jsonio.as_object(value=state.get(_SHORT_WINDOW_DEPARTURES)) or {}
    state[_SHORT_WINDOW_DEPARTURES] = {
        **remembered,
        account: {"resets_at": resets_at_value},
    }


def _short_window_departure_allows(
    *, profile: ProfileUsage, state: dict[str, object], now: float
) -> bool:
    remembered = jsonio.as_object(value=state.get(_SHORT_WINDOW_DEPARTURES))
    record = None if remembered is None else jsonio.as_object(value=remembered.get(profile.name))
    if record is None:
        return True
    raw_reset = record.get("resets_at")
    reset = resets_at(timestamp=raw_reset if isinstance(raw_reset, str) else None)
    usage = cast(UsageRecord, profile.usage)
    if reset == inf:
        return usage.five_hour_remaining >= _FULLY_REPLENISHED
    return now >= reset


def drain_target(
    *,
    profiles: tuple[ProfileUsage, ...],
    active: ActiveAccount,
    protection_floors: Mapping[str, float],
    state: dict[str, object],
    now: float,
) -> ProfileUsage | None:
    """The soonest-resetting account whose weekly reset precedes the active one."""
    active_reset = resets_at(timestamp=active.usage.seven_day_resets_at)
    if active_reset == inf:
        return None
    active_protected = (
        protection_floor_for(name=active.name, protection_floors=protection_floors) > 0.0
    )
    candidates = tuple(
        profile
        for profile in profiles
        if profile.name != active.name
        and profile.source == "live"
        and profile.usage is not None
        and (
            active_protected
            or not is_protected(profile=profile, protection_floors=protection_floors)
        )
        and profile.usage.seven_day_remaining
        >= max(
            weekly_reserve(),
            protection_floor_for(name=profile.name, protection_floors=protection_floors),
        )
        + min_headroom_gain()
        and profile.usage.five_hour_remaining >= five_hour_remaining_floor() + min_headroom_gain()
        and (
            not active.scoped_pin
            or (
                profile.usage.fable_remaining is not None
                and profile.usage.fable_remaining >= scoped_reserve() + min_headroom_gain()
            )
        )
        and resets_at(timestamp=profile.usage.seven_day_resets_at)
        <= active_reset - _RESET_TOLERANCE_S
        and _short_window_departure_allows(profile=profile, state=state, now=now)
    )
    ranked = tuple(
        sorted(
            candidates,
            key=lambda profile: (
                is_protected(profile=profile, protection_floors=protection_floors),
                resets_at(timestamp=cast(UsageRecord, profile.usage).seven_day_resets_at),
            ),
        )
    )
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
