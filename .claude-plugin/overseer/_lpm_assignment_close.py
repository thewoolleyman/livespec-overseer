"""The two times a close writes, and the idempotent ordered contributions beside them.

SPECIFICATION/contracts.md fixes `normalized_close_time` for report, completion and release as
the LATEST of the stored `lease_started_at`, the stored non-null `target_committed_at` and the
EARLIER of the stored `accepted_at` and `lease_expires_at`; requires `assignment-end-update` to
use that value as `actual_lease_ended_at` while `closed_at` uses the stored `accepted_at`; and
for expire requires both to be `lease_expires_at`. It further requires `report_markers` to be
an array of UNIQUE objects containing exactly `occurred_at` and a `classification` from the
report's closed set, sorted by `occurred_at` and then by the UTF-8 bytes of `classification`,
with `report-marker-update` inserting the new marker in that declared canonical order.

EVERY INPUT IS A STORED VALUE, AND THAT IS THE WHOLE ANTI-DRIFT PROPERTY. Not one of these
times is read from a clock here. `accepted_at` was captured once, immediately after the
operation's pre-validation, and every retry reuses it — so replaying a close computes the
SAME pair of times however much wall clock has passed, and two concurrent contributions to one
assignment cannot disagree about when its lease ended. A function that sampled a clock would
make a retry's answer depend on when the retry happened, which is exactly the drift an
idempotent command must not have.

THE CANONICAL ORDER IS A RE-SORT, NOT AN APPEND. Markers arrive in whatever order the
contributions do, so inserting one at the end would make the stored array's bytes depend on
arrival order — and two managers that applied the same two reports in different orders would
then hold different assignment bytes for the same facts. Re-sorting makes the stored array a
function of the SET of contributions.

RE-INSERTING AN EXISTING MARKER IS A COMPLETED NO-OP, not a duplicate and not a refusal. The
contract recognizes a repeat by the exact `(occurred_at, classification)` pair, so the second
arrival of one report contributes nothing and must leave the array byte-identical; a DUPLICATE
already sitting in the stored array is a different thing — a malformed local record — and fails
closed.

`closed_at` MAY PRECEDE `normalized_close_time`, and the contract says so explicitly: that
happens only after a BACKWARD wall-clock step, when the stored `lease_started_at` is later than
the `accepted_at` captured afterwards. The relation is therefore not asserted as an invariant
here, because asserting it would reject a durable state the contract admits.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_reports import ReportMarker
from _lpm_results import ManagerError, internal_bug, store_unavailable
from _lpm_signal import REPORT_CLASSIFICATIONS
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CLOSING_COMMANDS",
    "MARKER_MEMBERS",
    "CloseTimes",
    "assignment_end_defect",
    "close_times",
    "insert_report_marker",
    "marker_object",
    "normalized_close_time",
    "ordered_markers",
]

MARKER_MEMBERS: Final = ("occurred_at", "classification")
CLOSING_COMMANDS: Final = ("report", "complete", "release", "expire")

_EXPIRE: Final = "expire"


@dataclass(frozen=True, kw_only=True)
class CloseTimes:
    """The pair one close writes: when the lease actually ended, and when it closed.

    They are deliberately separate values rather than one instant. `actual_lease_ended_at` is
    about the LEASE and is clamped into the lease's own window; `closed_at` is about the
    COMMAND and records the instant it was accepted. Collapsing them would either move a
    lease's end outside its window or misreport when the operator acted.
    """

    actual_lease_ended_at: str
    closed_at: str


def marker_object(*, marker: ReportMarker) -> dict[str, str]:
    """The exact two-member mapping for one stored report marker."""
    return {"occurred_at": marker.occurred_at, "classification": marker.classification}


def ordered_markers(*, markers: Sequence[object]) -> Result[tuple[ReportMarker, ...], ManagerError]:
    """Validate a stored marker array and return it in the declared canonical order.

    A DUPLICATE in the stored array is a malformed local record rather than something to
    silently collapse: the array is defined to hold unique objects, and quietly de-duplicating
    it would hide a write that should never have happened.
    """
    validated: list[ReportMarker] = []
    for entry in markers:
        marker = _marker_from_object(parsed=entry)
        if isinstance(marker, Failure):
            return marker
        if marker.unwrap() in validated:
            return Failure(store_unavailable(message="report_markers must hold unique objects"))
        validated.append(marker.unwrap())
    return Success(_canonical_order(markers=validated))


def insert_report_marker(
    *, markers: Sequence[object], marker: ReportMarker
) -> Result[tuple[ReportMarker, ...], ManagerError]:
    """Insert `marker` into `markers` in canonical order, or leave it exactly as it is.

    The already-present case returns the SAME canonical array, so a repeated contribution is a
    completed no-op whose stored bytes are unchanged.
    """
    existing = ordered_markers(markers=markers)
    if isinstance(existing, Failure):
        return existing
    recorded = existing.unwrap()
    if marker in recorded:
        return Success(recorded)
    return Success(_canonical_order(markers=[*recorded, marker]))


def normalized_close_time(
    *,
    lease_started_at: str,
    lease_expires_at: str,
    target_committed_at: str | None,
    accepted_at: str,
) -> Result[str, ManagerError]:
    """The contract's `normalized_close_time` for a report, completion or release.

    Comparison is lexical, which is sound ONLY because this operation has exactly one
    fixed-width timestamp spelling; every input is therefore validated as that spelling first
    rather than compared on trust.
    """
    for name, value in (
        ("lease_started_at", lease_started_at),
        ("lease_expires_at", lease_expires_at),
        ("accepted_at", accepted_at),
    ):
        if not is_canonical_timestamp(text=value):
            return Failure(internal_bug(message=f"{name} must be a UTC RFC 3339-second timestamp"))
    if target_committed_at is not None and not is_canonical_timestamp(text=target_committed_at):
        return Failure(
            internal_bug(message="target_committed_at must be null or a canonical timestamp")
        )
    candidates = [lease_started_at, min(accepted_at, lease_expires_at)]
    if target_committed_at is not None:
        candidates.append(target_committed_at)
    return Success(max(candidates))


def close_times(
    *,
    command: str,
    lease_started_at: str,
    lease_expires_at: str,
    target_committed_at: str | None,
    accepted_at: str,
) -> Result[CloseTimes, ManagerError]:
    """The pair `command` writes when it closes an assignment.

    Expire is the one command whose closing instant is not its own acceptance: the lease simply
    ran out, so both values are `lease_expires_at` and the result does not depend on when the
    expiry was noticed.
    """
    if command not in CLOSING_COMMANDS:
        return Failure(internal_bug(message=f"{command} does not close an assignment"))
    normalized = normalized_close_time(
        lease_started_at=lease_started_at,
        lease_expires_at=lease_expires_at,
        target_committed_at=target_committed_at,
        accepted_at=accepted_at,
    )
    if isinstance(normalized, Failure):
        return normalized
    if command == _EXPIRE:
        return Success(
            CloseTimes(actual_lease_ended_at=lease_expires_at, closed_at=lease_expires_at)
        )
    return Success(CloseTimes(actual_lease_ended_at=normalized.unwrap(), closed_at=accepted_at))


def assignment_end_defect(
    *,
    lease_started_at: str,
    lease_expires_at: str,
    target_committed_at: str | None,
    actual_lease_ended_at: str,
) -> str | None:
    """A reason a stored `actual_lease_ended_at` falls outside its own lease window.

    The contract bounds it below by the LATER of `lease_started_at` and a non-null
    `target_committed_at` — a lease cannot have ended before its own target committed — and
    above by `lease_expires_at`, which is the whole point of a lease fence.
    """
    floor = lease_started_at
    if target_committed_at is not None:
        floor = max(floor, target_committed_at)
    if actual_lease_ended_at < floor:
        return "actual_lease_ended_at must be no earlier than the lease start and target commit"
    if actual_lease_ended_at > lease_expires_at:
        return "actual_lease_ended_at must be no later than lease_expires_at"
    return None


def _marker_from_object(*, parsed: object) -> Result[ReportMarker, ManagerError]:
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a report marker must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(MARKER_MEMBERS):
        return Failure(
            store_unavailable(
                message=f"a report marker must contain exactly {', '.join(MARKER_MEMBERS)}"
            )
        )
    occurred_at = source["occurred_at"]
    if not isinstance(occurred_at, str) or not is_canonical_timestamp(text=occurred_at):
        return Failure(
            store_unavailable(message="a marker occurred_at must be a canonical timestamp")
        )
    if source["classification"] not in REPORT_CLASSIFICATIONS:
        return Failure(
            store_unavailable(
                message=f"a marker classification must be one of: "
                f"{', '.join(REPORT_CLASSIFICATIONS)}"
            )
        )
    return Success(
        ReportMarker(occurred_at=occurred_at, classification=str(source["classification"]))
    )


def _canonical_order(*, markers: Sequence[ReportMarker]) -> tuple[ReportMarker, ...]:
    return tuple(
        sorted(markers, key=lambda marker: (marker.occurred_at, marker.classification.encode()))
    )
