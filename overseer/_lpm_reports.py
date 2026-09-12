"""Consumer failure reports: exact input, idempotent acknowledgement, typed consequences.

SPECIFICATION/contracts.md fixes the report object at exactly `version`, non-empty
`consumer_run_id` and `record_id`, a UTC RFC 3339-second `occurred_at`, a `classification` from
the closed four-member set, and an optional REDACTED `diagnostic` which — once accepted — MUST be
discarded before operation persistence and is excluded from normalized-input equality. It requires
a stored `(occurred_at, classification)` marker to return `duplicate` true BEFORE interval
validation and apply no effect; requires `occurred_at` to sit within the assignment's or
tombstone's interval and not be in the future; refuses a report against a currently `acquiring`
record because that record could not have been provisioned; makes the lifecycle move a compare-
and-set on the stored value generation, a NO-OP when generations differ or the record is already
`suspect`, `dead` or `reacquiring`; and leaves lifecycle status untouched for `unknown`.

IDEMPOTENCE IS BY MARKER, NOT BY OUTCOME, and the ordering is the subtle half. The duplicate
check runs before interval validation precisely so a report that was already ACCEPTED cannot
later be refused as out-of-interval merely because the assignment has since closed and its
interval shrank. A consumer retrying after a lost acknowledgement must get the same answer
it would have got the first time.

TWO DIFFERENT NO-OPS MEET HERE AND MUST NOT BE MERGED. A DUPLICATE applies nothing at all —
no lease release, no transition, no eviction — because the first report already did all of
it. A GENERATION MISMATCH or an already-`suspect` record applies the lease release and
nothing else: the report is ACCEPTED, the run is let go, and the REPLACEMENT credential's
lifecycle and cache entry are deliberately left alone. Collapsing the second into the first
would strand a lease; collapsing it into the ordinary path would suspect a credential the
reporting run never used.

`unknown` IS NOT A WEAK OUTAGE. It releases the lease and changes nothing else, so a
consumer that cannot say what happened cannot cost a credential its validity. The four
classifications' consequences are a flat table next door, not a severity ordering.

NOTHING HERE CARRIES CREDENTIAL MATERIAL. The accepted report is four scalars; a `diagnostic`
is checked mechanically and then DROPPED rather than stored, so there is no field through
which a token could reach an operation record, an audit entry or a result message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_lifecycle import REPORT_EVENT, admitted_move
from _lpm_record import CREDENTIAL_STATUSES
from _lpm_results import ManagerError, internal_bug, invalid_report
from _lpm_signal import REPORT_CLASSIFICATIONS, handling_for, is_redacted_diagnostic
from _lpm_time import is_at_or_after, is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "REPORT_OPTIONAL_MEMBERS",
    "REPORT_REQUIRED_MEMBERS",
    "REPORT_VERSION",
    "FailureReport",
    "ReportEffects",
    "ReportMarker",
    "occurred_within_interval",
    "report_effects",
    "report_from_object",
    "report_marker",
    "stored_marker",
]

REPORT_VERSION: Final = 1

REPORT_REQUIRED_MEMBERS: Final = (
    "version",
    "consumer_run_id",
    "record_id",
    "occurred_at",
    "classification",
)
REPORT_OPTIONAL_MEMBERS: Final = ("diagnostic",)

_ACQUIRING_STATUS: Final = "acquiring"


@dataclass(frozen=True, kw_only=True)
class FailureReport:
    """One accepted report: four scalars, and never the `diagnostic` that came with it."""

    consumer_run_id: str
    record_id: str
    occurred_at: str
    classification: str


@dataclass(frozen=True, kw_only=True)
class ReportMarker:
    """The stored idempotency marker: the pair a repeat is recognized by."""

    occurred_at: str
    classification: str


@dataclass(frozen=True, kw_only=True)
class ReportEffects:
    """What one report does, as four independent facts rather than one verdict."""

    duplicate: bool
    releases_lease: bool
    next_status: str | None
    evicts_cache_entry: bool


def report_marker(*, report: FailureReport) -> ReportMarker:
    """The marker `report` would store, so a later repeat of it is recognized."""
    return ReportMarker(occurred_at=report.occurred_at, classification=report.classification)


def stored_marker(*, report: FailureReport, markers: tuple[ReportMarker, ...]) -> bool:
    """Whether this exact time-and-classification pair is already recorded."""
    return report_marker(report=report) in markers


def report_from_object(*, parsed: object) -> Result[FailureReport, ManagerError]:
    """Validate one decoded report; an accepted `diagnostic` is checked and then DISCARDED."""
    if not isinstance(parsed, dict):
        return Failure(invalid_report(message="report must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    membership = _membership_refusal(source=source)
    if membership is not None:
        return Failure(membership)
    fields = _field_refusal(source=source)
    if fields is not None:
        return Failure(fields)
    return Success(
        FailureReport(
            consumer_run_id=str(source["consumer_run_id"]),
            record_id=str(source["record_id"]),
            occurred_at=str(source["occurred_at"]),
            classification=str(source["classification"]),
        )
    )


def occurred_within_interval(
    *, report: FailureReport, target_committed_at: str, lease_closes_at: str, now: str
) -> bool:
    """Whether `occurred_at` sits inside the assignment's or tombstone's closed interval.

    `lease_closes_at` is the assignment's `lease_expires_at` for a live assignment and the
    tombstone's `actual_lease_ended_at` for a closed one — the caller resolves which,
    because only it knows whether expiration recovery replaced the assignment.
    """
    return (
        is_at_or_after(moment=report.occurred_at, limit=target_committed_at) is True
        and is_at_or_after(moment=now, limit=report.occurred_at) is True
        and is_at_or_after(moment=lease_closes_at, limit=report.occurred_at) is True
    )


def report_effects(
    *,
    report: FailureReport,
    status: str,
    markers: tuple[ReportMarker, ...],
    generation_matches: bool,
) -> Result[ReportEffects, ManagerError]:
    """The effects `report` applies against a record currently in `status`."""
    if stored_marker(report=report, markers=markers):
        return Success(
            ReportEffects(
                duplicate=True, releases_lease=False, next_status=None, evicts_cache_entry=False
            )
        )
    handling = handling_for(classification=report.classification)
    if handling is None:
        return Failure(
            invalid_report(
                message=f"classification must be one of: {', '.join(REPORT_CLASSIFICATIONS)}"
            )
        )
    if status not in CREDENTIAL_STATUSES:
        return Failure(internal_bug(message=f"unregistered credential status: {status}"))
    if status == _ACQUIRING_STATUS:
        return Failure(
            invalid_report(message="an acquiring credential could not have been provisioned")
        )
    move = (
        admitted_move(status=status, event=REPORT_EVENT) if handling.suspects_credential else None
    )
    if move is None or not generation_matches:
        return Success(
            ReportEffects(
                duplicate=False,
                releases_lease=handling.releases_lease,
                next_status=None,
                evicts_cache_entry=False,
            )
        )
    return Success(
        ReportEffects(
            duplicate=False,
            releases_lease=handling.releases_lease,
            next_status=move.next_status,
            evicts_cache_entry=handling.evicts_cache_entry,
        )
    )


def _membership_refusal(*, source: dict[str, object]) -> ManagerError | None:
    missing = [member for member in REPORT_REQUIRED_MEMBERS if member not in source]
    if missing:
        return invalid_report(message=f"report is missing {missing[0]}")
    permitted = set(REPORT_REQUIRED_MEMBERS) | set(REPORT_OPTIONAL_MEMBERS)
    extra = sorted(set(source) - permitted)
    if extra:
        return invalid_report(message=f"report has extra member {extra[0]}")
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != REPORT_VERSION:
        return invalid_report(message="report version must be the integer 1")
    return None


def _field_refusal(*, source: dict[str, object]) -> ManagerError | None:
    for member in ("consumer_run_id", "record_id"):
        value = source[member]
        if not isinstance(value, str) or value == "":
            return invalid_report(message=f"{member} must be a non-empty string")
    occurred_at = source["occurred_at"]
    if not isinstance(occurred_at, str) or not is_canonical_timestamp(text=occurred_at):
        return invalid_report(message="occurred_at must be a UTC RFC 3339-second timestamp")
    if source["classification"] not in REPORT_CLASSIFICATIONS:
        return invalid_report(
            message=f"classification must be one of: {', '.join(REPORT_CLASSIFICATIONS)}"
        )
    return _diagnostic_refusal(source=source)


def _diagnostic_refusal(*, source: dict[str, object]) -> ManagerError | None:
    if "diagnostic" not in source:
        return None
    diagnostic = source["diagnostic"]
    if not isinstance(diagnostic, str):
        return invalid_report(message="diagnostic must be a string")
    if not is_redacted_diagnostic(diagnostic=diagnostic):
        return invalid_report(message="diagnostic is not mechanically redacted")
    return None
