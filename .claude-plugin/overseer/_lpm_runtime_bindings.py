"""Authoritative assignment and tombstone reads for runtime commands."""

from __future__ import annotations

from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import (
    COMMITTED_STATUS,
    Assignment,
    assignment_from_object,
    assignment_path,
)
from _lpm_localstate import read_local_record
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, invalid_report
from _lpm_runtime_base import RuntimeHost
from _lpm_tombstone import tombstone_from_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ReportBinding",
    "read_runtime_assignment",
    "report_binding",
]


@dataclass(frozen=True, kw_only=True)
class ReportBinding:
    """The report-relevant members of a committed assignment or retained tombstone."""

    tombstone: bool
    record_id: str
    target_committed_at: str
    closes_at: str
    markers: tuple[dict[str, str], ...]


def read_runtime_assignment(
    *, host: RuntimeHost, consumer_run_id: str
) -> Result[Assignment | None, ManagerError]:
    """Read and validate one run's live assignment."""
    path = assignment_path(state_dir=host.state_dir, consumer_run_id=consumer_run_id)
    if isinstance(path, Failure):
        return Failure(path.failure())
    stored = read_local_record(path=path.unwrap(), owner_uid=host.owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    if stored.unwrap() is None:
        return Success(None)
    return assignment_from_object(parsed=stored.unwrap())


def report_binding(
    *, host: RuntimeHost, consumer_run_id: str
) -> Result[ReportBinding, ManagerError]:
    """Read the authoritative tombstone first, otherwise the committed assignment."""
    tombstone = _stored_family(host=host, family="tombstone", consumer_run_id=consumer_run_id)
    if isinstance(tombstone, Failure):
        return Failure(tombstone.failure())
    if tombstone.unwrap() is not None:
        parsed = tombstone_from_object(parsed=tombstone.unwrap())
        if isinstance(parsed, Failure):
            return Failure(parsed.failure())
        closed = parsed.unwrap()
        return Success(
            ReportBinding(
                tombstone=True,
                record_id=closed.record_id,
                target_committed_at=closed.target_committed_at,
                closes_at=closed.actual_lease_ended_at,
                markers=closed.report_markers,
            )
        )
    assigned = read_runtime_assignment(host=host, consumer_run_id=consumer_run_id)
    if isinstance(assigned, Failure):
        return Failure(assigned.failure())
    assignment = assigned.unwrap()
    if assignment is None:
        return Failure(invalid_report(message="no assignment was issued for that consumer run"))
    return _assignment_binding(assignment=assignment)


def _assignment_binding(*, assignment: Assignment) -> Result[ReportBinding, ManagerError]:
    if assignment.status != COMMITTED_STATUS or assignment.target_committed_at is None:
        return Failure(invalid_report(message="a prepared assignment cannot accept reports"))
    return Success(
        ReportBinding(
            tombstone=False,
            record_id=assignment.record_id,
            target_committed_at=assignment.target_committed_at,
            closes_at=assignment.lease_expires_at,
            markers=assignment.report_markers,
        )
    )


def _stored_family(
    *, host: RuntimeHost, family: str, consumer_run_id: str
) -> Result[object | None, ManagerError]:
    path = local_record_path(state_dir=host.state_dir, family=family, identity=(consumer_run_id,))
    if isinstance(path, Failure):
        return Failure(path.failure())
    return read_local_record(path=path.unwrap(), owner_uid=host.owner_uid)
