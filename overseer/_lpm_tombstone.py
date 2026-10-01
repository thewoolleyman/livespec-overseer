"""The tombstone: a closed assignment's permanent record, and why reuse stays refused.

SPECIFICATION/contracts.md states the tombstone as containing EXACTLY `version`, the
assignment's normalized `request`, non-empty `target_ref`, `account_id`, `value_generation` and
`value_ref`, lowercase UUIDv4 `record_id`, UTC RFC 3339-second `lease_started_at`,
`lease_expires_at`, `target_committed_at`, `actual_lease_ended_at` and `closed_at`, plus its
`report_markers` and nullable `completion`. It carries NO `status` and NO `receipt`: a tombstone
is closed by construction, and the receipt was the live answer to a provision that is over.

EVERY TIME IS NON-NULL HERE, which is the difference that matters. An assignment's commit and
end times are nullable because it may still be prepared or still live; a tombstone exists only
because a committed assignment closed, so all five instants are known. A tombstone with a null
time is therefore malformed rather than merely incomplete — and since the initial manager
RETAINS every tombstone and its target binding INDEFINITELY, a malformed one is a permanent
hole in the record that refuses `consumer_run_id` reuse.

`closed_at` IS COMMAND-SPECIFIC, and the contract is explicit that it records a logical closing
instant rather than uniformly recording command acceptance: the stored `accepted_at` for report,
complete or release, and `lease_expires_at` for expire or a post-commit prepared-state expiry.
That is why `tombstone_from_assignment` takes the close times rather than computing them — the
command knows which instant closed it, and `_lpm_assignment_close` is where that choice lives.

TOMBSTONE CREATION COMMITS BEFORE ASSIGNMENT REMOVAL. While both files survive that crash
window the TOMBSTONE is authoritative and reuse remains refused, so the ordering is the safe
one: a crash between them leaves a closed binding readable twice rather than not at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment, assignment_object, shared_binding_defect
from _lpm_assignment_close import CloseTimes, assignment_end_defect, ordered_markers
from _lpm_operation_input import normalized_input_defect
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "TOMBSTONE_MEMBERS",
    "TOMBSTONE_VERSION",
    "Tombstone",
    "tombstone_from_assignment",
    "tombstone_from_object",
    "tombstone_object",
    "tombstone_path",
]

TOMBSTONE_VERSION: Final = 1

TOMBSTONE_MEMBERS: Final = (
    "version",
    "request",
    "target_ref",
    "account_id",
    "value_generation",
    "value_ref",
    "record_id",
    "lease_started_at",
    "lease_expires_at",
    "target_committed_at",
    "actual_lease_ended_at",
    "closed_at",
    "report_markers",
    "completion",
)

_REQUIRED_TIMES: Final = (
    "target_committed_at",
    "actual_lease_ended_at",
    "closed_at",
)


@dataclass(frozen=True, kw_only=True)
class Tombstone:
    """One closed assignment, retained indefinitely so its run identity stays consumed."""

    request: dict[str, object]
    target_ref: str
    account_id: str
    value_generation: str
    value_ref: str
    record_id: str
    lease_started_at: str
    lease_expires_at: str
    target_committed_at: str
    actual_lease_ended_at: str
    closed_at: str
    report_markers: tuple[dict[str, str], ...]
    completion: dict[str, object] | None


def tombstone_path(*, state_dir: Path, consumer_run_id: str) -> Result[Path, ManagerError]:
    """The deterministic owner-only path of `consumer_run_id`'s tombstone."""
    return local_record_path(state_dir=state_dir, family="tombstone", identity=(consumer_run_id,))


def tombstone_object(*, tombstone: Tombstone) -> dict[str, object]:
    """The exact fourteen-member mapping, built from the declared member list."""
    values: dict[str, object] = {"version": TOMBSTONE_VERSION}
    for member in TOMBSTONE_MEMBERS[1:]:
        values[member] = getattr(tombstone, member)
    values["report_markers"] = [dict(marker) for marker in tombstone.report_markers]
    return values


def tombstone_from_assignment(
    *, assignment: Assignment, close_times: CloseTimes
) -> Result[Tombstone, ManagerError]:
    """Derive the tombstone that closes `assignment` at `close_times`.

    Every binding member is copied from the assignment verbatim, so the closed record names the
    same reference, account, generation and value reference the live one did; only the two close
    instants are new, and they come from the command rather than from a clock read here.
    """
    if assignment.target_committed_at is None:
        return Failure(
            store_unavailable(message="only a committed assignment may become a tombstone")
        )
    source = assignment_object(assignment=assignment)
    for member in ("status", "receipt"):
        del source[member]
    source["actual_lease_ended_at"] = close_times.actual_lease_ended_at
    source["closed_at"] = close_times.closed_at
    source["version"] = TOMBSTONE_VERSION
    return tombstone_from_object(parsed=source)


def tombstone_from_object(*, parsed: object) -> Result[Tombstone, ManagerError]:
    """Validate one decoded tombstone; every one of its five instants must be present."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a tombstone must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    for inspect in (_membership_defect, _typed_defect):
        reason = inspect(source=source)
        if reason is not None:
            return Failure(store_unavailable(message=reason))
    markers = ordered_markers(markers=cast("list[object]", source["report_markers"]))
    if isinstance(markers, Failure):
        return markers
    return Success(
        Tombstone(
            request=cast("dict[str, object]", source["request"]),
            target_ref=str(source["target_ref"]),
            account_id=str(source["account_id"]),
            value_generation=str(source["value_generation"]),
            value_ref=str(source["value_ref"]),
            record_id=str(source["record_id"]),
            lease_started_at=str(source["lease_started_at"]),
            lease_expires_at=str(source["lease_expires_at"]),
            target_committed_at=str(source["target_committed_at"]),
            actual_lease_ended_at=str(source["actual_lease_ended_at"]),
            closed_at=str(source["closed_at"]),
            report_markers=tuple(
                {"occurred_at": marker.occurred_at, "classification": marker.classification}
                for marker in markers.unwrap()
            ),
            completion=cast("dict[str, object] | None", source["completion"]),
        )
    )


def _membership_defect(*, source: dict[str, object]) -> str | None:
    missing = [member for member in TOMBSTONE_MEMBERS if member not in source]
    if missing:
        return f"a tombstone is missing {missing[0]}"
    extra = sorted(set(source) - set(TOMBSTONE_MEMBERS))
    if extra:
        return f"a tombstone has extra member {extra[0]}"
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != TOMBSTONE_VERSION:
        return "a tombstone version must be the integer 1"
    return None


def _typed_defect(*, source: dict[str, object]) -> str | None:
    binding = shared_binding_defect(source=source)
    if binding is not None:
        return binding
    for member in _REQUIRED_TIMES:
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"a tombstone {member} must be a UTC RFC 3339-second timestamp"
    if not isinstance(source["report_markers"], list):
        return "a tombstone report_markers must be an array"
    window = assignment_end_defect(
        lease_started_at=str(source["lease_started_at"]),
        lease_expires_at=str(source["lease_expires_at"]),
        target_committed_at=str(source["target_committed_at"]),
        actual_lease_ended_at=str(source["actual_lease_ended_at"]),
    )
    if window is not None:
        return window
    completion = source["completion"]
    if completion is None:
        return None
    return normalized_input_defect(command="complete", normalized_input=completion)
