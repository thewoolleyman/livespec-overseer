"""The CAPACITY TEST: which candidates can carry the current load until the next pass.

A candidate the fleet would drain within one projection horizon is not a
destination, it is the next pass's problem: moving onto it costs a switch and
buys nothing, because the pass after this one has to move again, off an account
that is by then refusing. So each candidate's own balance is projected forward
exactly as the fast-drain trigger projects the active account's, against that
candidate's own share of the fleet load, and anyone the projection leaves at or
below the short-window floor is excluded.

IT NARROWS, IT NEVER RELAXES. Every candidate it is handed has already survived
every other rule, and it only ever removes rows from that set.

THE ONE CASE IT STANDS ASIDE FOR IS STATED BY THE RATIFIED CLAUSE rather than
inferred: a REFUSING active account serves nothing at all, while an account the
load drains before the next pass still serves until then -- so where a refusal
holds the active account and nothing passes the test, the test is RELEASED and
the pass selects among the failing candidates by the unchanged ranking. Note
what that is conditioned on: the refusal, not the emptiness. An ordinary pass
whose every candidate fails HOLDS, and it needs a line of its own to say so,
because the table printed beside it shows every one of those candidates above
its floor -- which is the whole point of projecting.
"""

from __future__ import annotations

from dataclasses import dataclass

from caam_burn_rate import projection_horizon_s
from caam_capacity_load import CapacityLoad
from caam_capacity_weights import capacity_weight
from caam_decision import ProfileUsage, five_hour_remaining_floor
from caam_rendering import with_reasons

__all__: list[str] = [
    "CapacitySelection",
    "capacity_hold_line",
    "capacity_release_note",
    "capacity_selection",
]


@dataclass(frozen=True, kw_only=True)
class CapacitySelection:
    """What the capacity test left a pass to select from.

    `profiles` is that set in the order it was handed: the admitted subset, or
    every candidate unchanged where the test was released, or empty.

    `excluded_every` is the one fact the emptiness cannot carry on its own. A
    set that was ALREADY empty when the test ran reads identically afterwards,
    and only one of the two is a capacity hold -- the other is an empty
    candidate set, whose own line names the gate that emptied it.
    """

    profiles: tuple[ProfileUsage, ...]
    excluded_every: bool = False
    released: bool = False


def capacity_selection(
    *,
    profiles: tuple[ProfileUsage, ...],
    load: CapacityLoad | None,
    refusal_held: bool,
) -> CapacitySelection:
    """Apply the test to a ranked candidate set, releasing it where ratified.

    With NO load the whole set is returned untouched. Failing closed instead
    would strand the fleet on an exhausted account on the one pass that knows
    least about the fleet -- the first pass after a restart, and every pass on a
    host whose demand nothing has yet measured.
    """
    if load is None:
        return CapacitySelection(profiles=profiles)
    admitted = tuple(profile for profile in profiles if _carries(profile=profile, load=load))
    # `not profiles` is what keeps an ALREADY-empty set out of the capacity
    # hold: there was no candidate for this test to exclude, so the pass owes
    # the empty-candidate-set diagnosis rather than a statement about the load.
    if admitted or not profiles:
        return CapacitySelection(profiles=admitted)
    if refusal_held:
        return CapacitySelection(profiles=profiles, released=True)
    return CapacitySelection(profiles=(), excluded_every=True)


def capacity_hold_line(*, reasons: tuple[str, ...] = ()) -> str:
    """The hold line for a pass whose every candidate the current load would drain.

    It states the load rather than the candidate set, because the set is not
    what went wrong: every account in it cleared every margin, and every figure
    in the table printed above reads healthy. The projection is the only thing
    that reconciles the hold with those figures.
    """
    return with_reasons(
        line="hold: no candidate can carry the current load until the next pass",
        reasons=reasons,
    )


def capacity_release_note() -> str:
    """The note a pass carries when a refusing active account released the test."""
    return (
        "note: capacity test was released because the refusal-held active account "
        "serves nothing and no candidate can carry the current load until the next pass"
    )


def _carries(*, profile: ProfileUsage, load: CapacityLoad) -> bool:
    """Whether this load leaves this candidate above the short-window floor.

    The comparison is the floor's own: at or below it excludes, strictly above
    admits, exactly as the trigger that reads the same floor on the active
    account does.

    A row whose usage read FAILED is left alone, because the projection has
    nothing to subtract from: this test narrows on EVIDENCE, and "no reading"
    is not a statement that the load would drain the account, it is the absence
    of any statement about the account at all. Such a row reaches here only on
    the drain arm, which hands over the raw selectable set and drops a dark row
    on its own live-row rule a step later; every other arm's eligibility rules
    have already dropped it. Excluding it here would reach that step with the
    row gone and could empty the set into a CAPACITY hold -- reporting a load
    nobody measured against it as the reason -- so the rule that owns the row
    keeps it.
    """
    usage = profile.usage
    if usage is None:
        return True
    short = usage.limit(kind="five_hour")
    if short is None:
        return True
    burn = load.projected_burn(weight=capacity_weight(capacity=profile.capacity))
    projected = short.remaining - burn * projection_horizon_s()
    return projected > five_hour_remaining_floor()
