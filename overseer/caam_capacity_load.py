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

WHICH IS WHY A LOAD IS REMEMBERED. The pass right after a switch is the one
whose selection most needs the test, and it is also the one pass that can
measure no rate at all -- the fall between its baseline and its reading spans
two accounts, so the rate is unknown by the very rule that keeps a fall from
being misattributed. The last measured load stands in for it, bounded at twice
the projection horizon: twice is what covers the pass after a switch whatever
the horizon is set to.

AN UNREADABLE ACTIVE CLASS YIELDS NO FLEET LOAD AT ALL, and the reason is that
there is nothing to divide by. The ratified clause makes such an account
contribute the weight of the candidate under test, which cancels the division
and leaves the measured rate itself as every candidate's projected burn -- so
the comparison is the one measurement this pass actually has, rather than a
product of it with a guess. Nothing is recorded either: a rate divided by no
weight is a statement about one account, and a later pass would read it as the
fleet's demand for up to twice the horizon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import jsonio
from caam_burn_rate import projection_horizon_s
from caam_capacity import AccountCapacity
from caam_capacity_weights import capacity_weight, capacity_weights
from caam_decision import ProfileUsage

__all__: list[str] = [
    "FLEET_LOAD",
    "CapacityLoad",
    "active_capacity",
    "capacity_load",
    "record_fleet_load",
]

FLEET_LOAD: Final = "fleet_load"
# How long a recorded load may stand in for a measured one, as a multiple of
# the projection horizon rather than a duration of its own: a fixed duration
# would stop covering the pass after a switch the moment an operator lengthened
# the horizon past it.
_STALE_AFTER_HORIZONS: Final = 2.0


@dataclass(frozen=True, kw_only=True)
class CapacityLoad:
    """The load the capacity test projects onto a candidate, in points per second.

    `load` is a FLEET load -- the rate an account of unit weight would fall at
    under the work the fleet is currently doing -- so one candidate's own
    projected burn is it divided by that candidate's capacity weight.

    `unweighted` says the ACTIVE account's class could not be read, in which
    case the figure carried is not a fleet load at all but the measured rate
    itself: the ratified clause has such an account contribute the weight of
    the candidate under test, so the division cancels. The FACT is carried
    rather than a per-candidate figure, which keeps the one division in the one
    place that performs it.
    """

    load: float
    unweighted: bool = False

    def projected_burn(self, *, weight: float) -> float:
        """How fast this work would drain a candidate of the given weight."""
        if self.unweighted:
            return self.load
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


def capacity_load(
    *,
    state: dict[str, object],
    burn: float | None,
    capacity: AccountCapacity | None,
    now: float,
) -> CapacityLoad | None:
    """The load this pass tests candidates against, or None where it has none.

    Read BEFORE `record_fleet_load`, for the same reason the burn rate is read
    before its own baseline is replaced: the load a pass without a rate falls
    back to is the one its PREDECESSOR measured, never one it has just written.
    """
    if burn is None:
        return _remembered_load(state=state, now=now)
    weight = _active_weight(capacity=capacity)
    if weight is None:
        return CapacityLoad(load=burn, unweighted=True)
    return CapacityLoad(load=burn * weight)


def record_fleet_load(
    *,
    state: dict[str, object],
    burn: float | None,
    capacity: AccountCapacity | None,
    refusal_held: bool,
    now: float,
) -> None:
    """Remember this pass's fleet load, where the ratified rule allows it to.

    Recorded with the INSTANT it was measured, because what a later pass may do
    with it depends on how old it is rather than on the figure alone.

    Three things withhold the record, and each is a case where the figure would
    be a statement about something other than the fleet's demand: an UNKNOWN
    rate (no measurement was made), an unreadable active CLASS (nothing to
    divide the rate by), and a REFUSAL holding the active account -- an account
    that is refusing serves a fraction of what the fleet asks of it, so its fall
    understates the demand, and this figure stands in for up to twice the
    horizon.
    """
    weight = _active_weight(capacity=capacity)
    if burn is None or weight is None or refusal_held:
        return
    state[FLEET_LOAD] = {"load": burn * weight, "at": now}


def _active_weight(*, capacity: AccountCapacity | None) -> float | None:
    """The ACTIVE account's capacity weight, or None where its class is unknown.

    Distinct from `capacity_weight`, which answers for a CANDIDATE and therefore
    has to answer with a number: a candidate of unknown class is weighted
    conservatively, while an unknown active account has no weight at all, and
    collapsing the two directions onto one function is what would make an
    unreadable plan silently conservative on the wrong side of the comparison.
    """
    if capacity is None or capacity.capacity_class not in capacity_weights():
        return None
    return capacity_weight(capacity=capacity)


def _remembered_load(*, state: dict[str, object], now: float) -> CapacityLoad | None:
    """The last recorded load, while it is no older than the ratified bound.

    A record the store cannot state in both halves -- a figure without an
    instant, or an instant without a figure -- is no load at all: how old a
    remembered load is governs whether it may be used, so a load whose age
    cannot be read is one whose eligibility cannot be judged.
    """
    stored = jsonio.as_object(value=state.get(FLEET_LOAD)) or {}
    load = jsonio.as_float(value=stored.get("load"))
    at = jsonio.as_float(value=stored.get("at"))
    if load is None or at is None:
        return None
    if now - at > _STALE_AFTER_HORIZONS * projection_horizon_s():
        return None
    return CapacityLoad(load=load)
