"""Completion-marker values and their exact, identity-unique proof-record parser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "COMPLETION_MARKER_MEMBERS",
    "CompletionMarker",
    "parse_completion_markers",
]

COMPLETION_MARKER_MEMBERS: Final = ("consumer_run_id", "record_id", "completed_at")


@dataclass(frozen=True, kw_only=True)
class CompletionMarker:
    """One qualifying completion's contribution identity and the instant it completed."""

    consumer_run_id: str
    record_id: str
    completed_at: str


def parse_completion_markers(
    *, entries: list[object]
) -> Result[tuple[CompletionMarker, ...], ManagerError]:
    """Parse the proof's ordered markers, refusing a repeated contribution identity."""
    collected: list[CompletionMarker] = []
    for entry in entries:
        marker = _marker_from_object(parsed=entry)
        if isinstance(marker, Failure):
            return marker
        identity = (marker.unwrap().consumer_run_id, marker.unwrap().record_id)
        if identity in [(held.consumer_run_id, held.record_id) for held in collected]:
            return Failure(
                store_unavailable(message="proof completion_markers must be unique by identity")
            )
        collected.append(marker.unwrap())
    return Success(tuple(collected))


def _marker_from_object(*, parsed: object) -> Result[CompletionMarker, ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a completion marker must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(COMPLETION_MARKER_MEMBERS):
        return Failure(
            store_unavailable(
                message=(
                    "a completion marker must contain exactly "
                    f"{', '.join(COMPLETION_MARKER_MEMBERS)}"
                )
            )
        )
    run_id = source["consumer_run_id"]
    if not isinstance(run_id, str) or run_id == "":
        return Failure(
            store_unavailable(message="a completion marker consumer_run_id must be non-empty")
        )
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return Failure(
            store_unavailable(message="a completion marker record_id must be a lowercase UUIDv4")
        )
    completed_at = source["completed_at"]
    if not isinstance(completed_at, str) or not is_canonical_timestamp(text=completed_at):
        return Failure(
            store_unavailable(message="a completion marker completed_at must be canonical")
        )
    return Success(
        CompletionMarker(consumer_run_id=run_id, record_id=record_id, completed_at=completed_at)
    )
