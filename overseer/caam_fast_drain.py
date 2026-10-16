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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from caam_burn_rate import projection_horizon_s
from caam_decision import UsageRecord

__all__: list[str] = [
    "FAST_DRAIN_TRIGGER",
    "ShortWindowProjection",
    "fast_drain_projection",
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


def fast_drain_projection(
    *, burn: float | None, current: UsageRecord
) -> ShortWindowProjection | None:
    """The projection this trigger fires on, or None where it does not fire.

    An UNKNOWN rate does not fire it, and neither does a non-positive one: a
    window that is not falling cannot be projected to reach anything.
    """
    if burn is None or burn <= 0:
        return None
    horizon = projection_horizon_s()
    return ShortWindowProjection(
        burn=burn,
        remaining=current.five_hour_remaining - burn * horizon,
        horizon=horizon,
    )
