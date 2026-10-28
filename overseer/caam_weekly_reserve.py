"""The weekly reserve decision made before candidate capacity selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import inf

from caam_capacity_load import CapacityLoad
from caam_capacity_select import capacity_selection
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    five_hour_remaining_floor,
    min_headroom_gain,
    weekly_reserve,
)
from caam_decision_protection import (
    CandidatePolicy,
    protection_floor_for,
    select_candidate_set,
)
from caam_extra_usage import spend_capped

__all__: list[str] = [
    "WeeklyReserveDecision",
    "WeeklyReserveRequest",
    "weekly_reserve_decision",
]


@dataclass(frozen=True, kw_only=True)
class WeeklyReserveDecision:
    """Whether the fleet-wide reserve remains enforced and its report note."""

    enforce: bool
    note: str | None


@dataclass(frozen=True, kw_only=True)
class WeeklyReserveRequest:
    """The facts that establish whether the weekly reserve remains in force."""

    profiles: tuple[ProfileUsage, ...]
    candidates: tuple[ProfileUsage, ...]
    active: ActiveAccount
    force: bool
    dimension: str
    protection_floors: Mapping[str, float]
    load: CapacityLoad | None
    active_fast_draining: bool
    active_refusal_held: bool


def weekly_reserve_decision(*, request: WeeklyReserveRequest) -> WeeklyReserveDecision:
    """Release only when no unprotected above-reserve account is usable now.

    The candidate check deliberately uses the ordinary margin with no scoped
    waiver and asks the capacity test with its refusal-held release disabled.
    The real selection applies the latter release only after this decision has
    admitted its candidate set.
    """
    reserve = weekly_reserve()
    above = _above_unprotected(
        profiles=request.profiles,
        active=request.active,
        protection_floors=request.protection_floors,
        reserve=reserve,
    )
    if _active_usable(
        active=request.active,
        above=above,
        active_fast_draining=request.active_fast_draining,
        active_refusal_held=request.active_refusal_held,
    ):
        return WeeklyReserveDecision(enforce=True, note=None)
    selectable = _usable_candidates(
        request=request,
        reserve=reserve,
    )
    above_names = frozenset(profile.name for profile in above)
    if any(profile.name in above_names for profile in selectable):
        return WeeklyReserveDecision(enforce=True, note=None)
    names = tuple(profile.name for profile in above)
    if not names:
        note = "note: weekly reserve was released because no unprotected account is above it"
    else:
        note = (
            "note: weekly reserve was released because no unprotected account above it was usable "
            f"({', '.join(names)})"
        )
    return WeeklyReserveDecision(enforce=False, note=note)


def _above_unprotected(
    *,
    profiles: tuple[ProfileUsage, ...],
    active: ActiveAccount,
    protection_floors: Mapping[str, float],
    reserve: float,
) -> tuple[ProfileUsage, ...]:
    rows = tuple(
        ProfileUsage(name=active.name, source="live", usage=active.usage)
        if profile.name == active.name
        else profile
        for profile in profiles
    )
    return tuple(
        profile
        for profile in rows
        if profile.usage is not None
        and profile.usage.seven_day_remaining >= reserve
        and protection_floor_for(name=profile.name, protection_floors=protection_floors) <= 0.0
    )


def _active_usable(
    *,
    active: ActiveAccount,
    above: tuple[ProfileUsage, ...],
    active_fast_draining: bool,
    active_refusal_held: bool,
) -> bool:
    return (
        any(profile.name == active.name for profile in above)
        and not active_fast_draining
        and not active_refusal_held
        and not spend_capped(usage=active.usage)
        and active.usage.five_hour_remaining > five_hour_remaining_floor()
    )


def _usable_candidates(
    *, request: WeeklyReserveRequest, reserve: float
) -> tuple[ProfileUsage, ...]:
    gain = (
        -inf
        if spend_capped(usage=request.active.usage)
        else (0.01 if request.force else min_headroom_gain())
    )
    admitted = select_candidate_set(
        profiles=tuple(
            profile
            for profile in request.candidates
            if profile.usage is not None
            and profile.usage.five_hour_remaining > five_hour_remaining_floor()
            and not spend_capped(usage=profile.usage)
        ),
        active_name=request.active.name,
        policy=CandidatePolicy(
            current=request.active.usage,
            gain_needed=gain,
            dimension=request.dimension,
            enforce_reserve=False,
            weekly_reserve=reserve,
            current_protection_floor=protection_floor_for(
                name=request.active.name,
                protection_floors=request.protection_floors,
            ),
        ),
        protection_floors=request.protection_floors,
    )
    return capacity_selection(profiles=admitted, load=request.load, refusal_held=False).profiles
