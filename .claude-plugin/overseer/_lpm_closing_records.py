"""The one live-assignment-or-tombstone read every closing effect settles against.

SPECIFICATION/contracts.md gives report, complete, release and expire two shapes of the same
phase: report `apply` and complete `apply` carry their full arrays "against a live assignment"
and only a leading prefix "against a tombstone", while "Tombstone creation MUST commit before
assignment removal; while both files survive that crash window, the tombstone is authoritative
and reuse remains refused". So every closing effect asks the same question first — which record
closes this run, and is it still live? — and that question is answered here once.

THE TOMBSTONE IS READ FIRST, AND THAT ORDER *IS* THE CONTRACT'S AUTHORITY RULE. A crash between
`tombstone-create` and `assignment-close` leaves BOTH files on disk, and the contract names the
tombstone authoritative for exactly that window. Reading the assignment first would make a
replay of `assignment-end-update` or `report-marker-update` write into a record that is already
superseded — and then `assignment-close` would delete the write.

A `prepared` ASSIGNMENT IS NOT CLOSEABLE, so it refuses rather than being treated as live. Its
`target_committed_at` is null by the status-field relations, and every close time is measured
against that instant; closing one would date a lease end from a target that never committed. It
also makes `target_committed_at` non-null for every record this module hands out, which is why
no closing effect re-checks it.

THE UPDATE WRITES BACK INTO THE FAMILY IT WAS READ FROM, never into the other one. That is the
whole reason `family` travels with the record: a tombstone-variant report inserts its marker in
the TOMBSTONE, and a live report inserts the same marker in the ASSIGNMENT, through one
executor that cannot tell them apart by anything else.

EVERY REPLACEMENT IS REVALIDATED THROUGH ITS OWN READER before it is written. A close computes
its times from stored values, and a stored assignment whose own commit instant sits outside its
lease window would make a normalized close time the record's relations forbid — so the write
refuses with `store-unavailable` instead of persisting a malformed record that no later reader
could accept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import assignment_from_object
from _lpm_assignment_close import CloseTimes, close_times
from _lpm_engine_context import EffectContext, input_text
from _lpm_engine_records import (
    RecordAction,
    satisfied_action,
    settle_record,
    stored_record,
    write_action,
)
from _lpm_reports import ReportMarker
from _lpm_results import ManagerError, store_unavailable
from _lpm_tombstone import tombstone_from_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ASSIGNMENT_FAMILY",
    "TOMBSTONE_FAMILY",
    "ClosingRecord",
    "closing_record",
    "closing_times",
    "settle_closing_update",
]

ASSIGNMENT_FAMILY: Final = "assignment"
TOMBSTONE_FAMILY: Final = "tombstone"

_CLOSING_FAMILIES: Final = (TOMBSTONE_FAMILY, ASSIGNMENT_FAMILY)


@dataclass(frozen=True, kw_only=True)
class ClosingRecord:
    """The record one closing effect acts on, and the family it must be written back to."""

    family: str
    consumer_run_id: str
    stored: dict[str, object]
    record_id: str
    value_generation: str
    report_markers: tuple[ReportMarker, ...]
    completion: dict[str, object] | None
    lease_started_at: str
    lease_expires_at: str
    target_committed_at: str


def closing_record(*, context: EffectContext) -> Result[ClosingRecord, ManagerError]:
    """The authoritative tombstone for this run, else its live committed assignment."""
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    for family in _CLOSING_FAMILIES:
        found = stored_record(context=context, family=family, identity=(run_id.unwrap(),))
        if isinstance(found, Failure):
            return Failure(found.failure())
        held = found.unwrap()
        if held is not None:
            return _closing(family=family, stored=held, consumer_run_id=run_id.unwrap())
    return Failure(
        store_unavailable(message="no live assignment or tombstone stands for this closing effect")
    )


def closing_times(
    *, context: EffectContext, record: ClosingRecord
) -> Result[CloseTimes, ManagerError]:
    """The lease-end and closing instants this command writes when it closes `record`.

    Every input is a stored value — the record's own lease window and target commit, and the
    operation's retained `accepted_at` — so a replay computes the same pair however much wall
    clock has passed since the command was accepted.
    """
    return close_times(
        command=context.operation.command,
        lease_started_at=record.lease_started_at,
        lease_expires_at=record.lease_expires_at,
        target_committed_at=record.target_committed_at,
        accepted_at=context.operation.accepted_at,
    )


def settle_closing_update(
    *, context: EffectContext, record: ClosingRecord, updated: dict[str, object]
) -> Result[str, ManagerError]:
    """Replace `record`'s own family entry with `updated`, or settle an already-equal one."""
    return settle_record(
        context=context,
        family=record.family,
        identity=(record.consumer_run_id,),
        decide=lambda held: _update_decision(held=held, family=record.family, updated=updated),
    )


def _update_decision(
    *, held: object | None, family: str, updated: dict[str, object]
) -> Result[RecordAction, ManagerError]:
    if held == updated:
        return Success(satisfied_action())
    validated = _validated(family=family, stored=updated)
    if isinstance(validated, Failure):
        return Failure(validated.failure())
    return Success(write_action(value=updated))


def _validated(*, family: str, stored: object) -> Result[object, ManagerError]:
    if family == TOMBSTONE_FAMILY:
        return tombstone_from_object(parsed=stored)
    return assignment_from_object(parsed=stored)


def _closing(
    *, family: str, stored: object, consumer_run_id: str
) -> Result[ClosingRecord, ManagerError]:
    if family == TOMBSTONE_FAMILY:
        return _from_tombstone(stored=stored, consumer_run_id=consumer_run_id)
    return _from_assignment(stored=stored, consumer_run_id=consumer_run_id)


def _from_tombstone(*, stored: object, consumer_run_id: str) -> Result[ClosingRecord, ManagerError]:
    validated = tombstone_from_object(parsed=stored)
    if isinstance(validated, Failure):
        return Failure(validated.failure())
    closed = validated.unwrap()
    return Success(
        ClosingRecord(
            family=TOMBSTONE_FAMILY,
            consumer_run_id=consumer_run_id,
            stored=cast("dict[str, object]", stored),
            record_id=closed.record_id,
            value_generation=closed.value_generation,
            report_markers=_markers(stored=closed.report_markers),
            completion=closed.completion,
            lease_started_at=closed.lease_started_at,
            lease_expires_at=closed.lease_expires_at,
            target_committed_at=closed.target_committed_at,
        )
    )


def _from_assignment(
    *, stored: object, consumer_run_id: str
) -> Result[ClosingRecord, ManagerError]:
    validated = assignment_from_object(parsed=stored)
    if isinstance(validated, Failure):
        return Failure(validated.failure())
    live = validated.unwrap()
    if live.target_committed_at is None:
        return Failure(
            store_unavailable(message="only a committed assignment may be closed or reported on")
        )
    return Success(
        ClosingRecord(
            family=ASSIGNMENT_FAMILY,
            consumer_run_id=consumer_run_id,
            stored=cast("dict[str, object]", stored),
            record_id=live.record_id,
            value_generation=live.value_generation,
            report_markers=_markers(stored=live.report_markers),
            completion=live.completion,
            lease_started_at=live.lease_started_at,
            lease_expires_at=live.lease_expires_at,
            target_committed_at=live.target_committed_at,
        )
    )


def _markers(*, stored: tuple[dict[str, str], ...]) -> tuple[ReportMarker, ...]:
    return tuple(
        ReportMarker(occurred_at=marker["occurred_at"], classification=marker["classification"])
        for marker in stored
    )
