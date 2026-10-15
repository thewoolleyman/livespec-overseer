"""Why a rotation pass ended with an empty candidate set, in the operator's words.

The hold line this feeds used to name ONE fixed cause for every empty candidate
set -- that no candidate had cleared the relative-headroom margin -- including the
sets where no comparison ever ran because nothing could be verified live. Read
against a table showing accounts at 100% weekly, that line contradicts its own
report, and the cause that actually applied was buried last in a list of three.

The predicates here mirror the gates `candidate_allowed` applies, in the same
order, so the cause named is the one that actually emptied the set. They are
DELIBERATELY not consulted when a target is chosen: nothing in this module can
admit or reject a candidate, it only decides which true sentence to print.

The refusal hold is the FIRST of those gates, applied before `candidate_allowed`
sees anything, so it is mirrored here as the first predicate rather than left
upstream as a filter on what this module is shown. Handed the already-filtered
set, the diagnosis cannot tell an account that is ABSENT from the vault from one
a refusal deliberately excluded, and reports the first -- which is the same
contradiction, against a table that still lists the held account's figures.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from caam_decision_models import ProfileUsage
from caam_decision_protection import protection_floor_for, weekly_left
from caam_extra_usage import spend_capped

__all__: list[str] = [
    "CandidatePopulation",
    "no_candidate_cause",
    "unverifiable_candidate_names",
]

# Every allowance is measured in what it has LEFT, so exhaustion is zero.
_NOTHING_LEFT = 0.0


@dataclass(frozen=True, kw_only=True)
class CandidatePopulation:
    """The rows a pass selected FROM, and the terms it judged them on.

    Carried as one value so the diagnosis reads exactly what selection read. The
    caller hands over its inputs rather than a verdict, which is what keeps this
    module incapable of influencing the choice it explains.

    ``profiles`` is every account in the vault, NOT the set the refusal hold
    left behind, and ``refusal_held`` names the ones that hold excluded. The two
    are carried separately because a cause that cannot tell them apart denies
    the held account exists.
    """

    profiles: tuple[ProfileUsage, ...]
    active_name: str
    dimension: str
    protection_floors: Mapping[str, float]
    refusal_held: frozenset[str] = frozenset()


def unverifiable_candidate_names(
    *, profiles: tuple[ProfileUsage, ...], active_name: str
) -> tuple[str, ...]:
    """Every account but the active one this pass could not verify live.

    The predicate is `candidate_allowed`'s own live-verification gate, so the set
    named here is exactly the set that gate excluded: a CACHED row, whose
    remembered figures the table still renders, belongs to it just as much as a
    fully dark one does. Naming only the dark rows tells the operator that one
    account was excluded while the rest were excluded silently, with figures still
    on display that read as usable.

    The ACTIVE account is left out because it is not a candidate to begin with --
    saying the account currently in use "was not considered" would trade one false
    statement for another.
    """
    return tuple(
        profile.name
        for profile in profiles
        if profile.name != active_name and not _live_verified(profile=profile)
    )


def no_candidate_cause(*, population: CandidatePopulation, gain_needed: float) -> str:
    """The gate that emptied the candidate set, named rather than guessed at.

    The margin appears only in the last clause, and only over candidates the
    margin was actually applied to. Where nothing could be verified live there is
    no comparison to report, and the line says so instead.

    A refusal-held account is named by none of the clauses below it, because no
    gate below ever judged it: saying it failed the margin would report a
    comparison that was never made against it. Which accounts a refusal excluded,
    and when each was recorded, is the refusal trigger's own reason to give.
    """
    active_name = population.active_name
    dimension = population.dimension
    others = tuple(profile for profile in population.profiles if profile.name != active_name)
    selectable = tuple(profile for profile in others if profile.name not in population.refusal_held)
    if not selectable:
        if others:
            return (
                f"no account other than {active_name} is selectable this pass, "
                f"so no {dimension} headroom comparison was made"
            )
        return (
            f"{active_name} is the only account in the vault, "
            f"so no {dimension} headroom comparison was made"
        )
    live = tuple(profile for profile in selectable if _live_verified(profile=profile))
    if not live:
        return (
            f"no account other than {active_name} could be verified live this pass "
            f"({_names(profiles=selectable)}), so no {dimension} headroom comparison was made"
        )
    spend_cap_excluded = tuple(profile for profile in live if spend_capped(usage=profile.usage))
    if spend_cap_excluded:
        return (
            "the extra-usage spend cap excludes these live-verified candidates "
            f"({_names(profiles=spend_cap_excluded)})"
        )
    if all(
        _exhausted(profile=profile, protection_floors=population.protection_floors)
        for profile in live
    ):
        return f"every live-verified candidate is exhausted ({_names(profiles=live)})"
    return (
        f"none of the live-verified candidates ({_names(profiles=live)}) clears the "
        f">={gain_needed:.2f} point {dimension} headroom margin over {active_name} "
        "within the weekly reserve"
    )


def _names(*, profiles: tuple[ProfileUsage, ...]) -> str:
    return ", ".join(profile.name for profile in profiles)


def _live_verified(*, profile: ProfileUsage) -> bool:
    """Both halves of `candidate_allowed`'s verification gate, kept together."""
    return profile.source == "live" and profile.usage is not None


def _exhausted(*, profile: ProfileUsage, protection_floors: Mapping[str, float]) -> bool:
    """Whether this candidate has nothing left to move onto, on either window.

    These are `is_eligible`'s two ABSOLUTE disqualifiers -- no weekly allowance
    left net of the account's own protection floor, or nothing left on the short
    window -- as opposed to its relative margin, which is a comparison rather
    than a property of the account and so cannot be reported per-account.
    """
    usage = profile.usage
    return usage is None or (
        weekly_left(
            usage=usage,
            protection_floor=protection_floor_for(
                name=profile.name, protection_floors=protection_floors
            ),
        )
        <= 0.0
        or usage.five_hour_remaining <= _NOTHING_LEFT
    )
