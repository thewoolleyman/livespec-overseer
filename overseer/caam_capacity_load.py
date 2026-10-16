"""The FLEET LOAD: how fast the work the fleet is doing drains an account.

A burn rate is a measurement of ONE account under the fleet's demand, and what
that rate says about any OTHER account depends on how much each of the two can
carry. Multiplying the active account's rate by its own capacity weight takes
the account back out of the figure and leaves the DEMAND: the rate at which an
account of unit weight would fall under the work the fleet is currently doing.
Dividing that by a candidate's own weight is what says how fast the same work
would drain the candidate.

An UNKNOWN rate yields no load rather than a zero one, and the difference
matters downstream: "the fleet is placing no load" would admit every candidate
as a positive statement about the fleet, where "no measurement was possible" is
a statement about this pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from caam_capacity import AccountCapacity
from caam_capacity_weights import capacity_weight
from caam_decision import ProfileUsage

__all__: list[str] = [
    "FLEET_LOAD",
    "CapacityLoad",
    "active_capacity",
    "capacity_load",
    "record_fleet_load",
]

FLEET_LOAD: Final = "fleet_load"


@dataclass(frozen=True, kw_only=True)
class CapacityLoad:
    """The load the capacity test projects onto a candidate, in points per second.

    `load` is a FLEET load -- the rate an account of unit weight would fall at
    under the work the fleet is currently doing -- so one candidate's own
    projected burn is it divided by that candidate's capacity weight.
    """

    load: float

    def projected_burn(self, *, weight: float) -> float:
        """How fast this work would drain a candidate of the given weight."""
        return self.load / weight


def active_capacity(
    *, profiles: tuple[ProfileUsage, ...], active_name: str
) -> AccountCapacity | None:
    """What this pass read about the ACTIVE account's plan, where it read anything.

    Taken off the polled rows rather than passed in beside them, because the
    active account IS one of those rows: a second channel for the same
    observation is a second thing that can disagree with the table printed
    above the decision.
    """
    return next(
        (profile.capacity for profile in profiles if profile.name == active_name),
        None,
    )


def capacity_load(*, burn: float | None, capacity: AccountCapacity | None) -> CapacityLoad | None:
    """The load this pass tests candidates against, or None where it has none."""
    if burn is None:
        return None
    return CapacityLoad(load=burn * capacity_weight(capacity=capacity))


def record_fleet_load(
    *,
    state: dict[str, object],
    burn: float | None,
    capacity: AccountCapacity | None,
    now: float,
) -> None:
    """Remember this pass's fleet load, where the ratified rule allows it to.

    Recorded with the INSTANT it was measured, because what a later pass may do
    with it depends on how old it is rather than on the figure alone.
    """
    if burn is None:
        return
    state[FLEET_LOAD] = {"load": burn * capacity_weight(capacity=capacity), "at": now}
