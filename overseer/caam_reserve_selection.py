"""Apply an already-made weekly-reserve decision to the normal candidate rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import inf

from caam_decision import (
    ActiveAccount,
    EligibleProfiles,
    ProfileUsage,
    min_headroom_gain,
    scoped_reserve,
    scoped_waiver_floor,
    weekly_reserve,
)
from caam_decision_protection import CandidatePolicy, protection_floor_for, select_candidate_set
from caam_extra_usage import spend_capped

__all__: list[str] = [
    "ReserveSelection",
    "eligible_profiles_for_reserve",
]


@dataclass(frozen=True, kw_only=True)
class ReserveSelection:
    """The already-decided weekly-reserve stance for one triggered pass."""

    enforce: bool
    note: str | None
    protection_floors: Mapping[str, float]


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
