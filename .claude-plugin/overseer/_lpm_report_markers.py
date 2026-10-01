"""The report-marker array an assignment carries: its order, its uniqueness, its encoding.

SPECIFICATION/contracts.md states the array exactly: "`report_markers` MUST be an array of
unique objects containing exactly UTC RFC 3339-second `occurred_at` and a `classification`
from the report's closed set, sorted by `occurred_at` and then by the UTF-8 bytes of
`classification`."

THE ORDER IS A CORRECTNESS PROPERTY, NOT TIDINESS. Two reports that differ only in arrival
order must leave BYTE-IDENTICAL records behind, because every later exact-match question --
"have I already accepted this report?", "is this stored completion the same one?" -- is asked
against those bytes. An array that merely appends encodes arrival history into the record, so
the same facts produce different state on a retry, and the idempotence the contract requires
becomes a property of timing.

UNIQUENESS IS ENFORCED HERE RATHER THAN AT THE CALL SITE for the same reason:
`_lpm_reports.stored_marker` answers whether a marker is ALREADY recorded, and a writer that
appended anyway would leave a record whose duplicate answer disagrees with its own contents.
`markers_with` is total -- appending a marker that is already present returns the array
unchanged -- so no caller has to remember to ask first.

THE SORT KEY IS THE CLASSIFICATION'S BYTES, NOT ITS PYTHON STRING ORDER. For the closed
classification set the two coincide today, and they would keep coinciding right up until a
classification carrying a non-ASCII character was registered. Encoding explicitly costs
nothing and makes the stated rule the implemented one.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_reports import ReportMarker
from _lpm_results import ManagerError, store_unavailable
from _lpm_signal import REPORT_CLASSIFICATIONS
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "REPORT_MARKER_MEMBERS",
    "marker_object",
    "markers_from_object",
    "markers_object",
    "markers_with",
    "sorted_markers",
]

REPORT_MARKER_MEMBERS: Final = ("occurred_at", "classification")


def marker_object(*, marker: ReportMarker) -> dict[str, object]:
    """The exact two-member marker mapping, built from the declared member list."""
    return {member: getattr(marker, member) for member in REPORT_MARKER_MEMBERS}


def markers_object(*, markers: Sequence[ReportMarker]) -> list[dict[str, object]]:
    """The whole array in its stored order; the caller has already sorted it."""
    return [marker_object(marker=marker) for marker in markers]


def sorted_markers(*, markers: Sequence[ReportMarker]) -> tuple[ReportMarker, ...]:
    """The contract's order: by `occurred_at`, then by the UTF-8 bytes of `classification`."""
    return tuple(
        sorted(markers, key=lambda marker: (marker.occurred_at, marker.classification.encode()))
    )


def markers_with(
    *, markers: Sequence[ReportMarker], marker: ReportMarker
) -> tuple[ReportMarker, ...]:
    """`markers` plus `marker`, in the contract's order — unchanged if it is already there."""
    if marker in tuple(markers):
        return tuple(markers)
    return sorted_markers(markers=(*markers, marker))


def markers_from_object(*, parsed: object) -> Result[tuple[ReportMarker, ...], ManagerError]:
    """Validate one decoded marker array, including its uniqueness AND its stored order.

    The stored ORDER is validated rather than repaired. A record whose array arrives out of
    order was not written by this module, so silently sorting it would hide the only evidence
    that something else has been writing manager state.
    """
    if not isinstance(parsed, list):
        return Failure(store_unavailable(message="report_markers must be a JSON array"))
    markers: list[ReportMarker] = []
    for element in cast("list[object]", parsed):
        decoded = _marker_from_object(parsed=element)
        if isinstance(decoded, Failure):
            return Failure(decoded.failure())
        markers.append(decoded.unwrap())
    if len(set(markers)) != len(markers):
        return Failure(store_unavailable(message="report_markers must be unique"))
    if tuple(markers) != sorted_markers(markers=markers):
        return Failure(
            store_unavailable(
                message="report_markers must sort by occurred_at then classification bytes"
            )
        )
    return Success(tuple(markers))


def _marker_from_object(*, parsed: object) -> Result[ReportMarker, ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a report marker must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(REPORT_MARKER_MEMBERS):
        return Failure(
            store_unavailable(
                message=f"a report marker carries exactly {', '.join(REPORT_MARKER_MEMBERS)}"
            )
        )
    occurred_at = source["occurred_at"]
    if not isinstance(occurred_at, str) or not is_canonical_timestamp(text=occurred_at):
        return Failure(
            store_unavailable(
                message="a report marker occurred_at must be a UTC RFC 3339-second timestamp"
            )
        )
    classification = source["classification"]
    if classification not in REPORT_CLASSIFICATIONS:
        return Failure(
            store_unavailable(
                message=(
                    "a report marker classification must be one of: "
                    f"{', '.join(REPORT_CLASSIFICATIONS)}"
                )
            )
        )
    return Success(ReportMarker(occurred_at=occurred_at, classification=str(classification)))
