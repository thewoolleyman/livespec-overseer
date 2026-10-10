"""Standalone internal relations for one serialized coexistence-proof record.

These checks use only bytes carried by the record.  They never consult assignments, tombstones or
the current clock, so retained proof remains readable after its source bindings disappear or the
wall clock moves backward.
"""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_time import is_canonical_timestamp

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "proof_relation_defect",
]

_SPREAD_MEMBERS: Final = (
    "first_consumer_run_id",
    "first_account_id",
    "second_consumer_run_id",
    "second_account_id",
    "overlap_started_at",
    "overlap_ended_at",
)
_SPREAD_TEXT_MEMBERS: Final = _SPREAD_MEMBERS[:4]
_SPREAD_TIME_MEMBERS: Final = _SPREAD_MEMBERS[4:]
_EVIDENCE_MEMBERS: Final = ("consumer_run_id", "completed_at")


def proof_relation_defect(*, source: dict[str, object]) -> str | None:
    """The first standalone relation violated by an otherwise shape-valid proof."""
    for inspect in (
        _dates_defect,
        _rollout_bounds_defect,
        _marker_order_defect,
        _spread_defect,
        _evidence_defect,
    ):
        reason = inspect(source=source)
        if reason is not None:
            return reason
    return None


def _dates_defect(*, source: dict[str, object]) -> str | None:
    raw_dates = cast("list[str]", source["successful_consumer_dates"])
    parsed_dates: list[date] = []
    for value in raw_dates:
        try:
            parsed_dates.append(date.fromisoformat(value))
        except ValueError:
            return "each proof successful_consumer_date must be a real UTC calendar date"
    for previous, current in pairwise(parsed_dates):
        if current != previous + timedelta(days=1):
            return "proof successful_consumer_dates must be sorted, unique and consecutive"
    soak = cast("str | None", source["soak_started_at"])
    if bool(raw_dates) != (soak is not None):
        return "proof dates must be non-empty exactly when soak_started_at is non-null"
    if raw_dates and raw_dates[0] != cast("str", soak)[:10]:
        return "the first proof date must equal the UTC date of soak_started_at"
    rollout = cast("str | None", source["rollout_started_at"])
    if parsed_dates and rollout is not None and parsed_dates[0] < date.fromisoformat(rollout[:10]):
        return "proof successful_consumer_dates must not precede rollout_started_at"
    return None


def _rollout_bounds_defect(*, source: dict[str, object]) -> str | None:
    rollout = cast("str | None", source["rollout_started_at"])
    if rollout is None:
        return None
    for member in ("soak_started_at", "last_auth_failure_at"):
        value = cast("str | None", source[member])
        if value is not None and value < rollout:
            return f"proof {member} must not precede rollout_started_at"
    for marker in cast("list[dict[str, object]]", source["completion_markers"]):
        if cast("str", marker["completed_at"]) < rollout:
            return "proof completion markers must not precede rollout_started_at"
    return None


def _marker_order_defect(*, source: dict[str, object]) -> str | None:
    markers = cast("list[dict[str, object]]", source["completion_markers"])
    keys = [
        (
            cast("str", marker["completed_at"]),
            cast("str", marker["consumer_run_id"]),
            cast("str", marker["record_id"]),
        )
        for marker in markers
    ]
    if keys != sorted(keys):
        return "proof completion_markers must be canonically ordered"
    return None


def _spread_defect(*, source: dict[str, object]) -> str | None:
    raw = source["simultaneous_spread"]
    if raw is None:
        return None
    spread = cast("dict[str, object]", raw)
    if sorted(spread) != sorted(_SPREAD_MEMBERS):
        return "proof simultaneous_spread has invalid membership"
    for inspect in (_spread_value_defect, _spread_identity_defect, _spread_interval_defect):
        reason = inspect(source=source, spread=spread)
        if reason is not None:
            return reason
    return None


def _spread_value_defect(*, source: dict[str, object], spread: dict[str, object]) -> str | None:
    _ = source
    for member in _SPREAD_TEXT_MEMBERS:
        value = spread[member]
        if not isinstance(value, str) or value == "":
            return f"proof simultaneous_spread {member} must be non-empty"
    for member in _SPREAD_TIME_MEMBERS:
        value = spread[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"proof simultaneous_spread {member} must be canonical"
    return None


def _spread_identity_defect(*, source: dict[str, object], spread: dict[str, object]) -> str | None:
    _ = source
    if spread["first_consumer_run_id"] == spread["second_consumer_run_id"]:
        return "proof simultaneous_spread run identities must differ"
    if spread["first_account_id"] == spread["second_account_id"]:
        return "proof simultaneous_spread account identities must differ"
    return None


def _spread_interval_defect(*, source: dict[str, object], spread: dict[str, object]) -> str | None:
    started = cast("str", spread["overlap_started_at"])
    ended = cast("str", spread["overlap_ended_at"])
    if ended < started:
        return "proof simultaneous_spread overlap must not end before it starts"
    rollout = cast("str", source["rollout_started_at"])
    if ended < rollout:
        return "proof simultaneous_spread overlap end must not precede rollout"
    return None


def _evidence_defect(*, source: dict[str, object]) -> str | None:
    rollout = cast("str | None", source["rollout_started_at"])
    for member in ("production_success", "legacy_pool_absence_success"):
        raw = source[member]
        if raw is None:
            continue
        evidence = cast("dict[str, object]", raw)
        if sorted(evidence) != sorted(_EVIDENCE_MEMBERS):
            return f"proof {member} has invalid membership"
        run_id = evidence["consumer_run_id"]
        if not isinstance(run_id, str) or run_id == "":
            return f"proof {member} consumer_run_id must be non-empty"
        completed_at = evidence["completed_at"]
        if not isinstance(completed_at, str) or not is_canonical_timestamp(text=completed_at):
            return f"proof {member} completed_at must be canonical"
        if rollout is not None and completed_at < rollout:
            return f"proof {member} completed_at must not precede rollout_started_at"
    return None
