"""Apply an already-made weekly-reserve decision to the normal candidate rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import inf

from caam_capacity_load import CapacityLoad
from caam_decision import (
    ActiveAccount,
    EligibleProfiles,
    ProfileUsage,
    five_hour_remaining_floor,
    min_headroom_gain,
    scoped_reserve,
    scoped_waiver_floor,
    weekly_reserve,
)
from caam_decision_protection import CandidatePolicy, protection_floor_for, select_candidate_set
from caam_extra_usage import spend_capped
from caam_release_note import empty_release_note
from caam_weekly_reserve import WeeklyReserveRequest, weekly_reserve_decision

__all__: list[str] = [
    "ReserveSelection",
    "ScheduledReserveSelectionRequest",
    "eligible_profiles_for_reserve",
    "scheduled_eligible_profiles",
]


@dataclass(frozen=True, kw_only=True)
class ReserveSelection:
    """The already-decided weekly-reserve stance for one triggered pass."""

    enforce: bool
    note: str | None
    protection_floors: Mapping[str, float]


@dataclass(frozen=True, kw_only=True)
class ScheduledReserveSelectionRequest:
    """The scheduled-pass facts used after its trigger arm has been resolved."""

    profiles: tuple[ProfileUsage, ...]
    candidates: tuple[ProfileUsage, ...]
    active: ActiveAccount
    active_name: str
    force: bool
    dimension: str
    protection_floors: Mapping[str, float]
    load: CapacityLoad | None
    active_fast_draining: bool
    active_refusal_held: bool


def eligible_profiles_for_reserve(
    *,
    profiles: tuple[ProfileUsage, ...],
    active: ActiveAccount,
    force: bool,
    dimension: str,
    selection: ReserveSelection,
) -> EligibleProfiles:
    """Apply a reserve decision while leaving every other candidate rule intact."""
    gain_needed = (
        -inf if spend_capped(usage=active.usage) else (0.01 if force else min_headroom_gain())
    )
    eligible = select_candidate_set(
        profiles=profiles,
        active_name=active.name,
        policy=CandidatePolicy(
            current=active.usage,
            gain_needed=gain_needed,
            dimension=dimension,
            enforce_reserve=selection.enforce,
            weekly_reserve=weekly_reserve(),
            scoped_reserve=scoped_reserve(),
            scoped_waiver_floor=scoped_waiver_floor(active=active),
            current_protection_floor=protection_floor_for(
                name=active.name,
                protection_floors=selection.protection_floors,
            ),
        ),
        protection_floors=selection.protection_floors,
    )
    return EligibleProfiles(
        profiles=eligible,
        reserve_released=not selection.enforce,
        note=selection.note,
    )


def scheduled_eligible_profiles(*, request: ScheduledReserveSelectionRequest) -> EligibleProfiles:
    """Apply the v070 reserve decision to a scheduled rotation pass only."""
    reserve = weekly_reserve_decision(
        request=WeeklyReserveRequest(
            profiles=request.profiles,
            candidates=request.candidates,
            active=request.active,
            force=request.force,
            dimension=request.dimension,
            protection_floors=request.protection_floors,
            load=request.load,
            active_fast_draining=request.active_fast_draining,
            active_refusal_held=request.active_refusal_held,
        )
    )
    admitted = request.candidates
    if not reserve.enforce:
        admitted = tuple(
            profile
            for profile in request.candidates
            if profile.usage is not None
            and profile.usage.five_hour_remaining > five_hour_remaining_floor()
        )
    eligible = eligible_profiles_for_reserve(
        profiles=admitted,
        active=request.active,
        force=request.force,
        dimension=request.dimension,
        selection=ReserveSelection(
            enforce=reserve.enforce,
            note=reserve.note,
            protection_floors=request.protection_floors,
        ),
    )
    if eligible.profiles or eligible.note is None:
        return eligible
    hold_note = empty_release_note(
        profiles=request.profiles,
        protection_floors=request.protection_floors,
        weekly_reserve=weekly_reserve(),
        active_name=request.active_name,
    )
    if hold_note.startswith("hold: protected account floors reached"):
        return EligibleProfiles(
            profiles=(),
            reserve_released=True,
            note=f"{hold_note}; {eligible.note}",
        )
    return eligible
