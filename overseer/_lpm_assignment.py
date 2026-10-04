"""The assignment record: one run's committed claim on one credential, and its status relations.

SPECIFICATION/contracts.md states the assignment as containing EXACTLY `version`, `status`
(`prepared` or `committed`), `request`, non-empty `target_ref`, `account_id`,
`value_generation` and `value_ref`, lowercase UUIDv4 `record_id`, `receipt`, UTC RFC
3339-second `lease_started_at` and `lease_expires_at`, nullable `target_committed_at` and
`actual_lease_ended_at`, `report_markers` and nullable `completion`.

THE STATUS-FIELD RELATIONS ARE THE LOAD-BEARING PART, and the contract says so outright: any
violation of them makes the record MALFORMED rather than merely odd. `target_committed_at` is
non-null EXACTLY when `status` is `committed`, and a `prepared` assignment must have a null end
time, an EMPTY marker array and a null completion. That pair of rules is what makes "did this
run's target actually commit?" answerable from the record alone — which is the question every
recovery path asks first, and the one a `prepared` record carrying a commit time would answer
wrongly in the direction that consumes a `consumer_run_id` forever.

`request` IS THE NORMALIZED PROVISIONING REQUEST, and `completion` IS THE COMPLETION INPUT, so
both are validated by the SAME validator the operation record uses for those commands rather
than by a second transcription here. A second spelling of either shape is how an assignment
comes to disagree with the operation that created it about what was asked for.

`receipt.validated_at` MUST equal the `last_validated` of the exact authoritative eligible
credential reread used to create the prepared assignment. That equality cannot be checked from
the record alone — the reread is gone — so it is the CREATE effect's obligation, asserted where
the reread is still in hand, and this module validates only the receipt's own shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment_close import assignment_end_defect, ordered_markers
from _lpm_operation_input import normalized_input_defect
from _lpm_paths import local_record_path
from _lpm_receipt import receipt_shape_defect
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ASSIGNMENT_MEMBERS",
    "ASSIGNMENT_STATUSES",
    "ASSIGNMENT_VERSION",
    "COMMITTED_STATUS",
    "PREPARED_STATUS",
    "Assignment",
    "assignment_from_object",
    "assignment_object",
    "assignment_path",
    "shared_binding_defect",
]

ASSIGNMENT_VERSION: Final = 1
PREPARED_STATUS: Final = "prepared"
COMMITTED_STATUS: Final = "committed"
ASSIGNMENT_STATUSES: Final = (PREPARED_STATUS, COMMITTED_STATUS)

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
_BINDING_TEXT_MEMBERS: Final = ("target_ref", "account_id", "value_ref")


@dataclass(frozen=True, kw_only=True)
class Assignment:
    """One run's prepared or committed assignment. Carries a reference, never a value."""

    status: str
    request: dict[str, object]
    target_ref: str
    account_id: str
    value_generation: str
    value_ref: str
    record_id: str
    receipt: dict[str, object]
    lease_started_at: str
    lease_expires_at: str
    target_committed_at: str | None
    actual_lease_ended_at: str | None
    report_markers: tuple[dict[str, str], ...]
    completion: dict[str, object] | None


def assignment_path(*, state_dir: Path, consumer_run_id: str) -> Result[Path, ManagerError]:
    """The deterministic owner-only path of `consumer_run_id`'s assignment."""
    return local_record_path(state_dir=state_dir, family="assignment", identity=(consumer_run_id,))


def assignment_object(*, assignment: Assignment) -> dict[str, object]:
    """The exact fifteen-member mapping, built from the declared member list."""
    values: dict[str, object] = {"version": ASSIGNMENT_VERSION}
    for member in ASSIGNMENT_MEMBERS[1:]:
        values[member] = getattr(assignment, member)
    values["report_markers"] = [dict(marker) for marker in assignment.report_markers]
    return values


def assignment_from_object(*, parsed: object) -> Result[Assignment, ManagerError]:
    """Validate one decoded assignment against its shape AND its status-field relations."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="an assignment must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    for inspect in (_membership_defect, _typed_defect, _status_defect):
        reason = inspect(source=source)
        if reason is not None:
            return Failure(store_unavailable(message=reason))
    markers = ordered_markers(markers=cast("list[object]", source["report_markers"]))
    if isinstance(markers, Failure):
        return markers
    return Success(
        Assignment(
            status=str(source["status"]),
            request=cast("dict[str, object]", source["request"]),
            target_ref=str(source["target_ref"]),
            account_id=str(source["account_id"]),
            value_generation=str(source["value_generation"]),
            value_ref=str(source["value_ref"]),
            record_id=str(source["record_id"]),
            receipt=cast("dict[str, object]", source["receipt"]),
            lease_started_at=str(source["lease_started_at"]),
            lease_expires_at=str(source["lease_expires_at"]),
            target_committed_at=_optional_text(value=source["target_committed_at"]),
            actual_lease_ended_at=_optional_text(value=source["actual_lease_ended_at"]),
            report_markers=tuple(
                {"occurred_at": marker.occurred_at, "classification": marker.classification}
                for marker in markers.unwrap()
            ),
            completion=cast("dict[str, object] | None", source["completion"]),
        )
    )


def shared_binding_defect(*, source: dict[str, object]) -> str | None:
    """A reason the binding members an assignment and its tombstone share are unusable.

    The two records name the SAME binding — one reference, one account, one credential
    generation and value reference, one record, one lease window — so the rule lives once and
    both callers ask it, rather than each transcribing the same six checks.
    """
    for member in _BINDING_TEXT_MEMBERS:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"an assignment {member} must be a non-empty string"
    for member in ("record_id", "value_generation"):
        value = source[member]
        if not isinstance(value, str) or not is_uuid4(value=value):
            return f"an assignment {member} must be a lowercase RFC 4122 UUIDv4"
    for member in ("lease_started_at", "lease_expires_at"):
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"an assignment {member} must be a UTC RFC 3339-second timestamp"
    return normalized_input_defect(command="provision", normalized_input=source["request"])


def _membership_defect(*, source: dict[str, object]) -> str | None:
    missing = [member for member in ASSIGNMENT_MEMBERS if member not in source]
    if missing:
        return f"an assignment is missing {missing[0]}"
    extra = sorted(set(source) - set(ASSIGNMENT_MEMBERS))
    if extra:
        return f"an assignment has extra member {extra[0]}"
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != ASSIGNMENT_VERSION:
        return "an assignment version must be the integer 1"
    return None


def _typed_defect(*, source: dict[str, object]) -> str | None:
    if source["status"] not in ASSIGNMENT_STATUSES:
        return f"an assignment status must be {' or '.join(ASSIGNMENT_STATUSES)}"
    binding = shared_binding_defect(source=source)
    if binding is not None:
        return binding
    receipt = receipt_shape_defect(receipt=source["receipt"])
    if receipt is not None:
        return receipt
    return _optional_member_defect(source=source)


def _optional_member_defect(*, source: dict[str, object]) -> str | None:
    for member in ("target_committed_at", "actual_lease_ended_at"):
        value = source[member]
        if value is not None and (
            not isinstance(value, str) or not is_canonical_timestamp(text=value)
        ):
            return f"an assignment {member} must be null or a UTC RFC 3339-second timestamp"
    if not isinstance(source["report_markers"], list):
        return "an assignment report_markers must be an array"
    completion = source["completion"]
    if completion is None:
        return None
    return normalized_input_defect(command="complete", normalized_input=completion)


def _status_defect(*, source: dict[str, object]) -> str | None:
    committed = source["status"] == COMMITTED_STATUS
    if committed != (source["target_committed_at"] is not None):
        return "target_committed_at must be non-null exactly when status is committed"
    if not committed:
        return _prepared_defect(source=source)
    ended = source["actual_lease_ended_at"]
    if ended is None:
        return None
    return assignment_end_defect(
        lease_started_at=str(source["lease_started_at"]),
        lease_expires_at=str(source["lease_expires_at"]),
        target_committed_at=str(source["target_committed_at"]),
        actual_lease_ended_at=str(ended),
    )


def _prepared_defect(*, source: dict[str, object]) -> str | None:
    if source["actual_lease_ended_at"] is not None:
        return "a prepared assignment must have a null actual_lease_ended_at"
    if cast("list[object]", source["report_markers"]) != []:
        return "a prepared assignment must have an empty report_markers array"
    if source["completion"] is not None:
        return "a prepared assignment must have a null completion"
    return None


def _optional_text(*, value: object) -> str | None:
    return None if value is None else str(value)
