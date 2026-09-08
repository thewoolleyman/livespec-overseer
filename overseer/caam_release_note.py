"""Why a pass could not use the released weekly reserve, in the operator's words.

This is REPORTING, not selection: nothing here is consulted to choose an
account, and the eligibility predicates beside it never read it back. It sits in
its own module for that reason -- it accreted inside the eligibility helpers,
where a reader looking for what admits a candidate had to step over prose that
admits nothing, and where it kept a file that has one job growing past the size
at which that job stays readable.

The dependency runs one way: this reads the protection helpers, and they are
unaware of it.
"""

from __future__ import annotations

from collections.abc import Mapping

from caam_decision_models import ProfileUsage
from caam_decision_protection import protection_floor_for, raw_weekly_left, weekly_left

__all__: list[str] = ["empty_release_note"]


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

    The release branch names LIVE-VERIFIED accounts because that is the population
    `every_live_account_under_reserve` measures, and the predicate is right to
    measure it: the release should turn on what is actually reachable. Saying
    "every account" claimed a scope it never consulted, and claimed it in the
    direction that makes a healthy fleet read as exhausted -- against the pass of
    2026-08-28 the one live account was under the reserve while three cached rows
    at 100%, 62% and 100% weekly were not, and were never asked.
    """
    candidates = tuple(profile for profile in profiles if profile.name != active_name)
    held = protected_accounts_at_floor(profiles=candidates, protection_floors=protection_floors)
    live_count = len(tuple(profile for profile in candidates if profile.source == "live"))
    if held and len(held) == live_count:
        accounts = ", ".join(
            f"{name} at {remaining:g}% left (floor {floor:g}%)" for name, remaining, floor in held
        )
        return f"hold: protected account floors reached: {accounts}"
    return (
        f"note: every live-verified account is under the {weekly_reserve:g}% "
        "weekly reserve -- releasing it"
    )


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
