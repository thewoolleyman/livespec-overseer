"""The CAPACITY WEIGHT of each capacity class, configured per provider.

A capacity class says how much an account can carry relative to the others; a
WEIGHT is that relation as a number, so a load measured on one account can be
divided by it to say what the same load would do to another. Only the RATIO
between two weights of one provider ever reaches a decision, which is why these
are per-provider tables rather than one fleet-wide scale.

THE NOMINAL PLAN MULTIPLIER IS NOT THE WEIGHT, and the defaults say so.
Anthropic's large plan is nominally twenty times its small one, while the
short-window fall measured on host hp 2026-10-13 was about seven to one -- and
the observed ratio is the one a load actually lands in. So the defaults carry
the measurement, and every one of them is a knob: a ratio measured once, on two
accounts, on one day, is evidence rather than a constant.

The medium default is deliberately LOW against that ratio, because no
medium-class ratio has been measured at all. Understating a class makes the
capacity test STRICTER for it, which is the direction an unmeasured figure
belongs in.
"""

from __future__ import annotations

import os
from typing import Final

from caam_capacity import LARGE, MEDIUM, SMALL, AccountCapacity

__all__: list[str] = [
    "ANTHROPIC",
    "capacity_weight",
    "capacity_weights",
]

ANTHROPIC: Final = "anthropic"

# contracts.md section "The account-rotation operation", paragraph **Capacity
# weights**. A provider added to rotation later states its own defaults, as a
# table of its own beside this one rather than as a fallback onto Anthropic's:
# a weight borrowed from another provider's measurements is not a measurement.
_DEFAULTS: Final[dict[str, dict[str, float]]] = {
    ANTHROPIC: {
        SMALL: 1.0,
        MEDIUM: 2.0,
        LARGE: 7.0,
    },
}


def capacity_weights(*, provider: str = ANTHROPIC) -> dict[str, float]:
    """Every configured weight for one provider, by capacity class."""
    return {
        capacity_class: _configured(
            provider=provider, capacity_class=capacity_class, default=default
        )
        for capacity_class, default in _DEFAULTS[provider].items()
    }


def capacity_weight(*, capacity: AccountCapacity | None, provider: str = ANTHROPIC) -> float:
    """The weight one account's observed capacity class carries.

    An account whose class could not be determined -- including one this pass
    made no observation of at all -- weighs as the SMALLEST class CONFIGURED for
    its provider, never as a hardcoded one. The ratified clause requires
    conservatism toward a candidate, and conservatism measured against a figure
    the operator has since changed is only conservative if it follows that
    figure.
    """
    weights = capacity_weights(provider=provider)
    if capacity is None or capacity.capacity_class not in weights:
        return min(weights.values())
    return weights[capacity.capacity_class]


def _configured(*, provider: str, capacity_class: str, default: float) -> float:
    configured = os.environ.get(
        f"CAAM_ROTATE_CAPACITY_WEIGHT_{provider.upper()}_{capacity_class.upper()}"
    )
    return default if configured is None else float(configured)
