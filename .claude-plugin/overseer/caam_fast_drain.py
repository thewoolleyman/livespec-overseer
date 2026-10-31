"""The FAST-DRAIN trigger: leave an account before it reaches the floor.

The short-window floor is a reading, and a reading is only ever a statement
about the moment it was taken. Between two passes an account on a small plan
under fleet load can spend the whole margin the floor was protecting, so a pass
that only ever compares the CURRENT balance against the floor leaves exactly
the account the floor exists to protect sitting on an exhausted window until the
pass after next.

So this trigger compares the PROJECTED balance instead: the account's remaining
figure less its burn rate across one projection horizon. Projecting across a
whole horizon already moves the fleet one pass early, which is why the operation
does not also shorten its schedule in response to a rate, and why the refusal
trigger remains the answer for an account whose reported figures lag what it
actually spent.

Its precedence is the lowest but one, stated under spec.md **Trigger
precedence**: the refusal trigger and every other trigger govern ahead of it,
and only the expiring-quota drain is lower.

ITS LINES LIVE HERE, beside the trigger, exactly as the expiring-quota drain's
and the refusal trigger's do: a trigger's own vocabulary belongs to the trigger.
They are the load-bearing half of this clause for anyone reading the log
afterwards, because the table printed beside the decision DISAGREES with it --
every figure in that table is above its floor, which is the whole point -- and
the rate and the projection are what reconcile the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, cast

from caam_burn_rate import projection_horizon_s
from caam_decision import (
    ProfileUsage,
    UsageRecord,
    five_hour_remaining_floor,
    fmt_duration,
    until,
)

__all__: list[str] = [
    "FAST_DRAIN_TRIGGER",
    "ShortWindowProjection",
    "fast_drain_projection",
    "fast_drain_switch_line",
    "fast_drain_trigger_line",
]

FAST_DRAIN_TRIGGER: Final = "projected-short-window-drain"


@dataclass(frozen=True, kw_only=True)
class ShortWindowProjection:
    """Where one account's short window is projected to be at the horizon.

    `burn` is in points per second, as measured; `horizon` travels with it so
    every surface that states a rate to an operator states it per horizon from
    the one pair of figures, rather than each one choosing its own unit.
    """

    burn: float
    remaining: float
    horizon: float

    @property
    def per_horizon(self) -> float:
        """The burn rate in short-window points per projection horizon.

        The unit every surface STATES the rate in, derived here rather than at
        each one: points per second is the unit a rate is measured in and reads
        as zero at every rate an operator cares about.
        """
        return self.burn * self.horizon


def fast_drain_projection(
    *, burn: float | None, current: UsageRecord
) -> ShortWindowProjection | None:
    """The projection this trigger fires on, or None where it does not fire.

    An UNKNOWN rate does not fire it, and neither does a non-positive one: a
    window that is not falling cannot be projected to reach anything. Nor does
    a rate that leaves the account ABOVE the floor at the end of the horizon --
    the trigger is about the projection reaching the floor, never about the
    account falling at all, and firing on any positive rate would move the
    fleet off every account that is being used.
    """
    if burn is None or burn <= 0:
        return None
    short = current.limit(kind="five_hour")
    if short is None:
        return None
    horizon = projection_horizon_s()
    remaining = short.remaining - burn * horizon
    if remaining > five_hour_remaining_floor():
        return None
    return ShortWindowProjection(burn=burn, remaining=remaining, horizon=horizon)


def fast_drain_trigger_line(
    *, active_name: str, current: UsageRecord, projection: ShortWindowProjection
) -> str:
    """Why this pass is leaving, in the figures the table cannot supply."""
    short = current.limit(kind="five_hour")
    if short is None:
        return "trigger: projected short-window drain unavailable without a short-window limit"
    return (
        "trigger: projected short-window drain -- "
        f"{active_name} has {short.remaining:.0f}% 5-hour left, "
        f"falling {projection.per_horizon:.0f}% per {_horizon(projection=projection)}, "
        f"projected {projection.remaining:.0f}% at the end of the horizon -- "
        "comparing candidates on five_hour"
    )


def fast_drain_switch_line(
    *,
    active_name: str,
    target: ProfileUsage,
    projection: ShortWindowProjection,
    now: float,
) -> str:
    """The switch line for a move made on this trigger, with its own reason."""
    usage = cast(UsageRecord, target.usage)
    short = usage.limit(kind="five_hour")
    if short is None:
        return f"SWITCHED {active_name} -> {target.name} (target has no short-window limit)"
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    return (
        f"SWITCHED {active_name} -> {target.name} "
        "(projected short-window drain; burn "
        f"{projection.per_horizon:.0f}% per {_horizon(projection=projection)}, "
        f"projected {projection.remaining:.0f}% at the end of the horizon; target has "
        f"{short.remaining:.0f}% 5-hour left, resets in "
        f"{until(timestamp=short.resets_at, now=now_dt)})"
    )


def _horizon(*, projection: ShortWindowProjection) -> str:
    """The horizon the rate is stated per, in the shape every duration is shown in."""
    return fmt_duration(seconds=projection.horizon)
