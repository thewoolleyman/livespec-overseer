"""The assignment record: what a successful provision leaves behind for later commands to read.

SPECIFICATION/contracts.md states the record exactly, and this module implements that member
list verbatim: "An assignment record MUST contain exactly `version` (integer `1`), `status`
(`prepared` or `committed`), `request`, non-empty `target_ref`, `account_id`,
`value_generation` and `value_ref`, lowercase RFC 4122 UUIDv4 `record_id`, `receipt`, UTC RFC
3339-second `lease_started_at` and `lease_expires_at`, nullable UTC RFC 3339-second
`target_committed_at` and `actual_lease_ended_at`, `report_markers` and nullable
`completion`." Its path is the contract's `consumer_run_id`-keyed local record, which is why
`consumer_run_id` is not a member: it is carried by the normalized `request`, and it is the
identity the FILENAME encodes.

WHY THE RECORD EXISTS AT ALL, stated plainly because it is the thing that was missing.
`_lpm_provision.provision` returns a receipt and persists nothing, and `_lpm_reports` can
compute a report's effects only when handed the markers already recorded — so before this
record there was nowhere for a marker to live, and the manager could not be idempotent across
two processes however carefully either one behaved. This is that state, and `with_marker` is
its only writer.

ABSENCE AND UNAVAILABILITY STAY APART. `read_assignment` answers `None` for a
`consumer_run_id` this manager never issued an assignment for, which is a FACT about that run
and lets `report` refuse it as `invalid-report` rather than blaming the store; a record that
exists and cannot be trusted takes the failure rail as `store-unavailable`. Collapsing the two
would make an unreadable record indistinguishable from a run that never happened, and the
manager would then cheerfully accept a first report against state it could not read.

THE STORED ORDER OF `report_markers` IS VALIDATED, NOT REPAIRED — see `_lpm_report_markers`
for why. The `completion` member is carried OPAQUELY: its shape belongs to the `complete`
command, and validating it here would put that command's grammar in two places.

EVERY WRITE GOES THROUGH `write_local_record`, which stages beside the destination and
renames, so a crash mid-write leaves the PRIOR record intact rather than a torn one. That is
what lets a report's marker append be safe to retry: either the whole new array landed or
none of it did.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record, write_local_record
from _lpm_paths import local_record_path
from _lpm_provision import ProvisionReceipt, ProvisionRequest, receipt_object
from _lpm_provision_request import provision_request_from_object, provision_request_object
from _lpm_receipt import receipt_from_object
from _lpm_record import is_uuid4
from _lpm_report_markers import markers_from_object, markers_object, markers_with
from _lpm_reports import ReportMarker
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ASSIGNMENT_FAMILY",
    "ASSIGNMENT_MEMBERS",
    "ASSIGNMENT_STATUSES",
    "ASSIGNMENT_VERSION",
    "COMMITTED_ASSIGNMENT",
    "PREPARED_ASSIGNMENT",
    "Assignment",
    "assignment_from_object",
    "assignment_object",
    "assignment_path",
    "read_assignment",
    "with_marker",
    "write_assignment",
]

ASSIGNMENT_VERSION: Final = 1
ASSIGNMENT_FAMILY: Final = "assignment"
PREPARED_ASSIGNMENT: Final = "prepared"
COMMITTED_ASSIGNMENT: Final = "committed"
ASSIGNMENT_STATUSES: Final = (PREPARED_ASSIGNMENT, COMMITTED_ASSIGNMENT)

ASSIGNMENT_MEMBERS: Final = (
    "version",
    "status",
    "request",
    "target_ref",
    "account_id",
    "value_generation",
    "value_ref",
    "record_id",
    "receipt",
    "lease_started_at",
    "lease_expires_at",
    "target_committed_at",
    "actual_lease_ended_at",
    "report_markers",
    "completion",
)

_NON_EMPTY_MEMBERS: Final = ("target_ref", "account_id", "value_generation", "value_ref")
_LEASE_TIMESTAMPS: Final = ("lease_started_at", "lease_expires_at")
_NULLABLE_TIMESTAMPS: Final = ("target_committed_at", "actual_lease_ended_at")


@dataclass(frozen=True, kw_only=True)
class Assignment:
    """One run's assignment: which credential it holds, until when, and what it has reported."""

    status: str
    request: ProvisionRequest
    target_ref: str
    account_id: str
    value_generation: str
    value_ref: str
    record_id: str
    receipt: ProvisionReceipt
    lease_started_at: str
    lease_expires_at: str
    target_committed_at: str | None
    actual_lease_ended_at: str | None
    report_markers: tuple[ReportMarker, ...]
    completion: object | None


def assignment_object(*, assignment: Assignment) -> dict[str, object]:
    """The exact fifteen-member assignment mapping, in the declared member order."""
    values: dict[str, object] = {"version": ASSIGNMENT_VERSION}
    for member in ASSIGNMENT_MEMBERS[1:]:
        values[member] = getattr(assignment, member)
    values["request"] = provision_request_object(request=assignment.request)
    values["receipt"] = receipt_object(receipt=assignment.receipt)
    values["report_markers"] = markers_object(markers=assignment.report_markers)
    return values


def with_marker(*, assignment: Assignment, marker: ReportMarker) -> Assignment:
    """A copy of `assignment` whose marker array also holds `marker`, in the contract's order."""
    return replace(
        assignment, report_markers=markers_with(markers=assignment.report_markers, marker=marker)
    )


def assignment_path(*, state_dir: Path, consumer_run_id: str) -> Result[Path, ManagerError]:
    """The deterministic `<manager-state>/assignments/<digest>.json` path for one run."""
    return local_record_path(
        state_dir=state_dir, family=ASSIGNMENT_FAMILY, identity=[consumer_run_id]
    )


def read_assignment(
    *, state_dir: Path, consumer_run_id: str, owner_uid: int
) -> Result[Assignment | None, ManagerError]:
    """This run's assignment, or `None` when the manager never issued one for it."""
    path = assignment_path(state_dir=state_dir, consumer_run_id=consumer_run_id)
    if isinstance(path, Failure):
        return Failure(path.failure())
    stored = read_local_record(path=path.unwrap(), owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    parsed = stored.unwrap()
    if parsed is None:
        return Success(None)
    decoded = assignment_from_object(parsed=parsed)
    if isinstance(decoded, Failure):
        return Failure(decoded.failure())
    return Success(decoded.unwrap())


def write_assignment(
    *, state_dir: Path, assignment: Assignment, owner_uid: int
) -> Result[None, ManagerError]:
    """Atomically replace this run's assignment record with `assignment`."""
    path = assignment_path(state_dir=state_dir, consumer_run_id=assignment.request.consumer_run_id)
    if isinstance(path, Failure):
        return Failure(path.failure())
    return write_local_record(
        path=path.unwrap(), value=assignment_object(assignment=assignment), owner_uid=owner_uid
    )


def assignment_from_object(*, parsed: object) -> Result[Assignment, ManagerError]:
    """Validate one decoded assignment record; an untrustworthy one is `store-unavailable`."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="an assignment must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    defect = _scalar_defect(source=source)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    return _assignment_with_members(source=source)


def _scalar_defect(*, source: dict[str, object]) -> str | None:
    if sorted(source) != sorted(ASSIGNMENT_MEMBERS):
        return f"an assignment carries exactly {', '.join(ASSIGNMENT_MEMBERS)}"
    version = source["version"]
    if isinstance(version, bool) or version != ASSIGNMENT_VERSION:
        return "assignment version must be the integer 1"
    if source["status"] not in ASSIGNMENT_STATUSES:
        return f"assignment status must be one of: {', '.join(ASSIGNMENT_STATUSES)}"
    return _identity_defect(source=source)


def _identity_defect(*, source: dict[str, object]) -> str | None:
    for member in _NON_EMPTY_MEMBERS:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"assignment {member} must be a non-empty string"
    for member in ("record_id", "value_generation"):
        if not is_uuid4(value=str(source[member])):
            return f"assignment {member} must be a lowercase RFC 4122 UUIDv4"
    if not isinstance(source["completion"], dict | type(None)):
        return "assignment completion must be a JSON object or null"
    return _timestamp_defect(source=source)


def _timestamp_defect(*, source: dict[str, object]) -> str | None:
    for member in _LEASE_TIMESTAMPS:
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"assignment {member} must be a UTC RFC 3339-second timestamp"
    for member in _NULLABLE_TIMESTAMPS:
        value = source[member]
        if value is None:
            continue
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"assignment {member} must be a UTC RFC 3339-second timestamp or null"
    return None


def _assignment_with_members(*, source: dict[str, object]) -> Result[Assignment, ManagerError]:
    request = provision_request_from_object(parsed=source["request"])
    if isinstance(request, Failure):
        return Failure(store_unavailable(message="assignment request is not a normalized request"))
    receipt = receipt_from_object(parsed=source["receipt"])
    if isinstance(receipt, Failure):
        return Failure(receipt.failure())
    markers = markers_from_object(parsed=source["report_markers"])
    if isinstance(markers, Failure):
        return Failure(markers.failure())
    return Success(
        Assignment(
            status=str(source["status"]),
            request=request.unwrap(),
            target_ref=str(source["target_ref"]),
            account_id=str(source["account_id"]),
            value_generation=str(source["value_generation"]),
            value_ref=str(source["value_ref"]),
            record_id=str(source["record_id"]),
            receipt=receipt.unwrap(),
            lease_started_at=str(source["lease_started_at"]),
            lease_expires_at=str(source["lease_expires_at"]),
            target_committed_at=_optional(value=source["target_committed_at"]),
            actual_lease_ended_at=_optional(value=source["actual_lease_ended_at"]),
            report_markers=markers.unwrap(),
            completion=source["completion"],
        )
    )


def _optional(*, value: object) -> str | None:
    return None if value is None else str(value)
