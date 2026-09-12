"""Per-field validators and bounds for the manager configuration object.

SPECIFICATION/contracts.md states each optional key's default
and its permitted range, and requires a wrong JSON type, invalid enum, non-unique array,
value outside those bounds or unregistered adapter or backend name to return
`invalid-request` with exit `2` BEFORE any store, health-adapter, acquisition-browser or
provisioning-target access. These validators are the "before" half of that sentence: they
run on a parsed object and touch nothing.

`True` IS NOT AN INTEGER HERE, even though Python says otherwise. `bool` is an `int`
subclass, so a bare `isinstance(value, int)` accepts JSON `true` and silently yields `1`
— which would pass `1 <= value <= 300` and configure a one-second validation age from a
configuration that never named a number. Every integer check therefore rejects `bool`
first. The same trap is already documented in this package's `jsonio.as_float`.

Split from `_lpm_config` by cohesion rather than by line count: this file answers "is one
field acceptable on its own", and the assembly module answers "do the accepted fields
agree with each other and with the registry".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "HEALTH_STRATEGIES",
    "INTEGER_FIELDS",
    "IntegerField",
    "enum_field",
    "integer_field",
    "name_list_field",
]

HEALTH_STRATEGIES: Final = ("none", "remaining-percent")


@dataclass(frozen=True, kw_only=True)
class IntegerField:
    """One configured integer key: its inclusive bounds and its default."""

    name: str
    low: int
    high: int
    default: int


INTEGER_FIELDS: Final[tuple[IntegerField, ...]] = (
    IntegerField(name="maximum_validation_age_seconds", low=1, high=300, default=300),
    IntegerField(name="backend_cache_interval_seconds", low=1, high=300, default=300),
    IntegerField(name="provider_probe_timeout_seconds", low=1, high=300, default=30),
    IntegerField(name="external_call_timeout_seconds", low=1, high=300, default=30),
    IntegerField(name="acquisition_worker_timeout_seconds", low=60, high=86400, default=7200),
    IntegerField(name="acquisition_step_limit", low=1, high=200, default=50),
    IntegerField(name="health_floor_percent", low=0, high=100, default=10),
    IntegerField(name="browser_attention_wait_seconds", low=1, high=3600, default=600),
)


def integer_field(*, field: IntegerField, value: object) -> Result[int, ManagerError]:
    """Accept `value` as `field`'s integer, or refuse with a secret-free reason."""
    if isinstance(value, bool) or not isinstance(value, int):
        return Failure(invalid_request(message=f"{field.name} must be an integer"))
    if value < field.low or value > field.high:
        return Failure(
            invalid_request(message=f"{field.name} must be from {field.low} through {field.high}")
        )
    return Success(value)


def enum_field(*, name: str, value: object, permitted: Sequence[str]) -> Result[str, ManagerError]:
    """Accept `value` as one of `permitted`, or refuse naming the closed set."""
    if not isinstance(value, str) or value not in permitted:
        return Failure(invalid_request(message=f"{name} must be one of: {', '.join(permitted)}"))
    return Success(value)


def name_list_field(
    *, name: str, value: object, registered: Sequence[str]
) -> Result[tuple[str, ...], ManagerError]:
    """Accept `value` as a non-empty array of unique, registered, non-empty names.

    Uniqueness is checked before registration so a duplicated-but-registered entry is
    reported as the duplicate it is; either way the array is refused whole rather than
    de-duplicated, because silently accepting a malformed array hides the edit that made
    it malformed.
    """
    if not isinstance(value, list) or value == []:
        return Failure(invalid_request(message=f"{name} must be a non-empty array"))
    entries = cast("list[object]", value)
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, str) or entry == "":
            return Failure(invalid_request(message=f"{name} entries must be non-empty strings"))
        names.append(entry)
    if len(set(names)) != len(names):
        return Failure(invalid_request(message=f"{name} entries must be unique"))
    unregistered = [entry for entry in names if entry not in registered]
    if unregistered:
        return Failure(invalid_request(message=f"{name} names an unregistered {unregistered[0]}"))
    return Success(tuple(names))
