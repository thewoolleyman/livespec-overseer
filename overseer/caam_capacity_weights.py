"""Failing stub: the CAPACITY WEIGHT of each capacity class, per provider."""

from __future__ import annotations

from typing import Final

from caam_capacity import AccountCapacity

__all__: list[str] = [
    "ANTHROPIC",
    "capacity_weight",
    "capacity_weights",
]

ANTHROPIC: Final = "anthropic"


def capacity_weights(*, provider: str = ANTHROPIC) -> dict[str, float]:
    del provider
    return {}


def capacity_weight(*, capacity: AccountCapacity | None, provider: str = ANTHROPIC) -> float:
    del capacity, provider
    return 0.0
