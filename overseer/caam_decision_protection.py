"""Protection and eligibility helpers for caam account rotation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import inf

from caam_decision_models import ProfileUsage, UsageRecord

__all__: list[str] = [
    "CandidatePolicy",
    "can_serve_scoped_model",
    "candidate_allowed",
    "dimension_spent",
    "empty_release_note",
    "floor_breach",
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
    # None disables the scoped-model waiver entirely, which is the state under
    # every input that carries no operator pin on the scoped model and under
    # every input where the ACTIVE account can still serve that pin. A float is
    # the short-window ceiling a scoped-capable candidate must stay below to be
    # admitted without clearing the relative-headroom margin, so the operation
    # never moves onto an account it would immediately have to leave again.
    scoped_waiver_ceiling: float | None = None


def can_serve_scoped_model(*, usage: UsageRecord | None) -> bool:
    """Whether this account's own scoped-model allowance can serve a pinned scoped model.

    Determined from the BALANCE alone, mirroring the shipped enforcement
    predicate: present and not fully spent. Fail-closed by construction — an
    account whose scoped allowance cannot be read (no usage record at all, or a
    record carrying no scoped figure) counts as unable to serve, never as able.
    A model that is available but not answering for non-quota reasons is outside
    what selection can observe and is the operator pin's concern, not this one's.
    """
    return usage is not None and usage.fable is not None and usage.fable < _FULLY_SPENT


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


def floor_breach(
    *, usage: UsageRecord | None, protection_floor: float
) -> tuple[float, float] | None:
    """Remaining and floor for a protected account at or past its floor, else None.

    Returns None whenever no floor is configured, so a caller can pass the result
    straight through and an unprotected account renders byte-identically to before.
    """
    if usage is None or protection_floor <= 0.0:
        return None
    if weekly_left(usage=usage, protection_floor=protection_floor) > 0.0:
        return None
    return (raw_weekly_left(usage=usage), protection_floor)


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
            gain_needed=_gain_needed_for(policy=policy, usage=profile.usage),
            dimension=policy.dimension,
            protection_floor=protection_floor,
        )
    )


def _gain_needed_for(*, policy: CandidatePolicy, usage: UsageRecord) -> float:
    """The headroom margin this candidate must clear, waived only under the scoped clause.

    The waiver is expressed as a margin of negative infinity rather than as a
    branch around `is_eligible`, and that is load-bearing: every OTHER
    disqualifier `is_eligible` applies -- the comparison dimension being one of
    the two defined ones, a candidate at zero weekly remaining, a candidate at
    its own protection floor, a candidate whose short-window allowance is fully
    spent -- keeps applying unchanged. The clause waives the relative-headroom
    margin and nothing else.
    """
    ceiling = policy.scoped_waiver_ceiling
    if ceiling is not None and can_serve_scoped_model(usage=usage) and usage.five_hour < ceiling:
        return -inf
    return policy.gain_needed


def empty_release_note(
    *,
    profiles: tuple[ProfileUsage, ...],
    protection_floors: Mapping[str, float],
    weekly_reserve: float,
    active_name: str = "",
) -> str:
    """Why the pass could not use the released reserve, in the operator's words.

    The protected-floor branch is judged over the CANDIDATES -- every live account
    other than the active one -- because the ratified clause is about every remaining
    CANDIDATE being at its floor. Judging it over the full set silently demands that
    the ACTIVE account be protected and at its floor too, which is a stricter and
    different condition.
    """
    candidates = tuple(profile for profile in profiles if profile.name != active_name)
    held = protected_accounts_at_floor(profiles=candidates, protection_floors=protection_floors)
    live_count = len(tuple(profile for profile in candidates if profile.source == "live"))
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
