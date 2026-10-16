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
"""

from __future__ import annotations

from typing import cast

from caam_burn_rate import projection_horizon_s
from caam_capacity_load import CapacityLoad
from caam_capacity_weights import capacity_weight
from caam_decision import ProfileUsage, UsageRecord, five_hour_remaining_floor

__all__: list[str] = [
    "capacity_selection",
]


def capacity_selection(
    *, profiles: tuple[ProfileUsage, ...], load: CapacityLoad | None
) -> tuple[ProfileUsage, ...]:
    """The candidates that can carry this load, in the order they were handed.

    With NO load the whole set is returned untouched. Failing closed instead
    would strand the fleet on an exhausted account on the one pass that knows
    least about the fleet -- the first pass after a restart, and every pass on a
    host whose demand nothing has yet measured.
    """
    if load is None:
        return profiles
    return tuple(profile for profile in profiles if _carries(profile=profile, load=load))


def _carries(*, profile: ProfileUsage, load: CapacityLoad) -> bool:
    """Whether this load leaves this candidate above the short-window floor.

    The comparison is the floor's own: at or below it excludes, strictly above
    admits, exactly as the trigger that reads the same floor on the active
    account does.
    """
    usage = cast(UsageRecord, profile.usage)
    burn = load.projected_burn(weight=capacity_weight(capacity=profile.capacity))
    projected = usage.five_hour_remaining - burn * projection_horizon_s()
    return projected > five_hour_remaining_floor()
