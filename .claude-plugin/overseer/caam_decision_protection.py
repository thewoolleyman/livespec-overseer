"""Protection and eligibility helpers for caam account rotation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import inf

from caam_decision_models import ProfileUsage, UsageRecord

__all__: list[str] = [
    "CandidatePolicy",
    "candidate_allowed",
    "dimension_spent",
    "empty_release_note",
    "is_eligible",
    "protection_floor_for",
    "raw_weekly_left",
    "select_candidate_set",
    "weekly_left",
]

_FULLY_SPENT = 100.0
NO_PROTECTION_FLOORS: Mapping[str, float] = {}


@dataclass(frozen=True, kw_only=True)
class CandidatePolicy:
    current: UsageRecord
    gain_needed: float
    dimension: str
    enforce_reserve: bool
    weekly_reserve: float


def weekly_left(*, usage: UsageRecord, protection_floor: float = 0.0) -> float:
    return max(0.0, 100.0 - usage.seven_day - protection_floor)


def raw_weekly_left(*, usage: UsageRecord) -> float:
    return 100.0 - usage.seven_day


def dimension_spent(*, usage: UsageRecord, dimension: str, protection_floor: float = 0.0) -> float:
    if dimension == "seven_day":
        return 100.0 - weekly_left(usage=usage, protection_floor=protection_floor)
    return {"five_hour": usage.five_hour}.get(dimension, inf)


def protection_floor_for(
    *, name: str | None, protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS
) -> float:
    if name is None:
        return 0.0
    return max(0.0, protection_floors.get(name, 0.0))


def is_eligible(
    *,
    usage: UsageRecord | None,
    current: UsageRecord,
    gain_needed: float,
    dimension: str,
    protection_floor: float = 0.0,
    current_protection_floor: float = 0.0,
) -> bool:
    return (
        usage is not None
        and dimension in {"five_hour", "seven_day"}
        and dimension_spent(
            usage=current,
            dimension=dimension,
            protection_floor=current_protection_floor,
        )
        - dimension_spent(usage=usage, dimension=dimension, protection_floor=protection_floor)
        >= gain_needed
        and weekly_left(usage=usage, protection_floor=protection_floor) > 0.0
        and usage.five_hour < _FULLY_SPENT
    )


def is_protected(*, profile: ProfileUsage, protection_floors: Mapping[str, float]) -> bool:
    return protection_floor_for(name=profile.name, protection_floors=protection_floors) > 0.0


def select_candidate_set(
    *,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    policy: CandidatePolicy,
    protection_floors: Mapping[str, float],
) -> tuple[ProfileUsage, ...]:
    unprotected = tuple(
        profile
        for profile in profiles
        if candidate_allowed(
            profile=profile,
            active_name=active_name,
            policy=policy,
            protection_floor=0.0,
        )
        and not is_protected(profile=profile, protection_floors=protection_floors)
    )
    if unprotected:
        return unprotected
    return tuple(
        profile
        for profile in profiles
        if candidate_allowed(
            profile=profile,
            active_name=active_name,
            policy=policy,
            protection_floor=protection_floor_for(
                name=profile.name,
                protection_floors=protection_floors,
            ),
        )
        and is_protected(profile=profile, protection_floors=protection_floors)
    )


def candidate_allowed(
    *,
    profile: ProfileUsage,
    active_name: str,
    policy: CandidatePolicy,
    protection_floor: float = 0.0,
) -> bool:
    return (
        profile.name != active_name
        and profile.source == "live"
        and profile.usage is not None
        and (
            not policy.enforce_reserve or weekly_left(usage=profile.usage) >= policy.weekly_reserve
        )
        and is_eligible(
            usage=profile.usage,
            current=policy.current,
            gain_needed=policy.gain_needed,
            dimension=policy.dimension,
            protection_floor=protection_floor,
        )
    )


def empty_release_note(
    *,
    profiles: tuple[ProfileUsage, ...],
    protection_floors: Mapping[str, float],
    weekly_reserve: float,
) -> str:
    held = protected_accounts_at_floor(profiles=profiles, protection_floors=protection_floors)
    live_count = len(tuple(profile for profile in profiles if profile.source == "live"))
    if held and len(held) == live_count:
        accounts = ", ".join(
            f"{name} at {remaining:g}% left (floor {floor:g}%)" for name, remaining, floor in held
        )
        return f"hold: protected account floors reached: {accounts}"
    return f"note: every account is under the {weekly_reserve:g}% weekly reserve -- releasing it"


def protected_accounts_at_floor(
    *, profiles: tuple[ProfileUsage, ...], protection_floors: Mapping[str, float]
) -> tuple[tuple[str, float, float], ...]:
    return tuple(
        (
            profile.name,
            raw_weekly_left(usage=profile.usage),
            protection_floor_for(name=profile.name, protection_floors=protection_floors),
        )
        for profile in profiles
        if profile.source == "live"
        and profile.usage is not None
        and protection_floor_for(name=profile.name, protection_floors=protection_floors) > 0.0
        and weekly_left(
            usage=profile.usage,
            protection_floor=protection_floor_for(
                name=profile.name,
                protection_floors=protection_floors,
            ),
        )
        == 0.0
    )
