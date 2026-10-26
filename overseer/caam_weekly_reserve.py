"""The weekly-reserve decision that precedes triggered rotation selection."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from caam_decision_models import ProfileUsage
from caam_decision_protection import NO_PROTECTION_FLOORS, protection_floor_for
from caam_extra_usage import spend_capped

__all__: list[str] = [
    "WeeklyReserveDecision",
    "can_serve_now",
    "weekly_reserve_decision",
]


@dataclass(frozen=True, kw_only=True)
class WeeklyReserveDecision:
    """Whether this pass must release its weekly reserve and the operator note."""

    released: bool
    note: str | None


def can_serve_now(*, profile: ProfileUsage, short_floor: float) -> bool:
    """Whether one live-verified account can serve a request before the next pass."""
    usage = profile.usage
    return (
        profile.source == "live"
        and usage is not None
        and not spend_capped(usage=usage)
        and usage.five_hour_remaining > short_floor
    )


def weekly_reserve_decision(
    *,
    profiles: tuple[ProfileUsage, ...],
    usable_names: Iterable[str],
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
    reserve: float,
) -> WeeklyReserveDecision:
    """Release unless an unprotected above-reserve account survived this pass's rules."""
    usable = frozenset(usable_names)
    above = tuple(
        profile.name
        for profile in profiles
        if profile.usage is not None
        and profile.usage.seven_day_remaining > reserve
        and protection_floor_for(name=profile.name, protection_floors=protection_floors) == 0.0
    )
    if any(name in usable for name in above):
        return WeeklyReserveDecision(released=False, note=None)
    if not above:
        return WeeklyReserveDecision(
            released=True,
            note="note: weekly reserve was released because no unprotected account is above it",
        )
    return WeeklyReserveDecision(
        released=True,
        note=(
            "note: weekly reserve was released because no unprotected account above it "
            f"was usable ({', '.join(above)})"
        ),
    )
