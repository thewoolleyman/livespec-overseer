"""The `report` command: accept one consumer failure signal, exactly once, and change nothing else.

SPECIFICATION/contracts.md fixes the answer shape -- "A successful report MUST emit
`{"version":1,"status":"ok","operation":"report","duplicate":<boolean>}`" -- and narrows the
failures: "`report` MAY emit only `invalid-request` for configuration failure, `invalid-report`,
`store-unavailable` or `internal-bug`."

THE DUPLICATE ANSWER IS SETTLED FROM LOCAL STATE ALONE, BEFORE ANY STORE ACCESS, and that
ordering is the whole of this command's idempotence. A replayed report is answered from the
assignment's own marker array: no SecretStore read, no credential, no lease touched, nothing
written. So a consumer that retries after a timeout gets the same answer on a host whose store
is unreachable as on one whose store is healthy, which is exactly what an idempotent operation
owes a caller that cannot tell whether its first attempt landed.

AN UNKNOWN RUN IS `invalid-report`, NOT `store-unavailable`. `read_assignment` reports absence
and untrustworthiness separately for this reason: a report naming a run this manager never
issued an assignment for is a defective REPORT, and blaming the store there would send an
operator to look at 1Password for a consumer's bug.

NOTHING IS MUTATED UNTIL EVERY REQUIRED EFFECT IS KNOWN TO BE POSSIBLE. The contract makes a
report's effects conditional on its classification: three of the four closed classifications
suspect the credential, which means a lifecycle transition, and all four release the lease. This
command computes the whole effect set first and refuses -- with nothing changed -- if any part of
it cannot be performed. The alternative, recording the marker and quietly dropping the status
transition, would leave a credential the provider has just rejected sitting at `valid` for the
next consumer to select, while telling this consumer its report was accepted.

THE DIAGNOSTIC IS CHECKED AND DISCARDED by `report_from_object`, so no part of it reaches this
module and nothing here can leak it. `FailureReport` deliberately has no `diagnostic` field.
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment, read_assignment, with_marker, write_assignment
from _lpm_command_host import (
    CommandOutcome,
    ManagerHost,
    error_outcome,
    read_command_object,
    run_serialization,
    success_outcome,
)
from _lpm_leases import release_lease
from _lpm_locks import release_lock
from _lpm_paths import local_record_path
from _lpm_record import CredentialRecord
from _lpm_reports import (
    FailureReport,
    ReportEffects,
    occurred_within_interval,
    report_effects,
    report_from_object,
    report_marker,
    stored_marker,
)
from _lpm_results import ManagerError, invalid_report, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "LEASE_FAMILY",
    "REPORT_OPERATION",
    "run_report_command",
]

REPORT_OPERATION: Final = "report"
LEASE_FAMILY: Final = "lease"

# Named rather than written as literals at the return sites: `Success(True)` is a boolean positional
# that reads as a flag, and these two are the command's ANSWER -- whether this exact report had
# already been accepted.
_DUPLICATE: Final = True
_ACCEPTED: Final = False


def run_report_command(*, source: str, host: ManagerHost) -> CommandOutcome:
    """Validate, match the assignment, answer a replay from local state, else apply the effects."""
    parsed = read_command_object(source=source, read_input=host.read_input, refuse=invalid_report)
    if isinstance(parsed, Failure):
        return error_outcome(error=parsed.failure())
    report = report_from_object(parsed=parsed.unwrap())
    if isinstance(report, Failure):
        return error_outcome(error=report.failure())
    accepted = report.unwrap()
    held = run_serialization(host=host, consumer_run_id=accepted.consumer_run_id)
    if isinstance(held, Failure):
        return error_outcome(error=held.failure())
    try:
        duplicate = _serialized(report=accepted, host=host)
    finally:
        release_lock(held=held.unwrap())
    if isinstance(duplicate, Failure):
        return error_outcome(error=duplicate.failure())
    return success_outcome(payload={"operation": REPORT_OPERATION, "duplicate": duplicate.unwrap()})


def _serialized(*, report: FailureReport, host: ManagerHost) -> Result[bool, ManagerError]:
    """Answer a replay from local state, else carry this report's operation to completion."""
    matched = _matched_assignment(report=report, host=host)
    if isinstance(matched, Failure):
        return Failure(matched.failure())
    assignment, target_committed_at = matched.unwrap()
    if stored_marker(report=report, markers=assignment.report_markers):
        return Success(_DUPLICATE)
    applied = _applied(
        report=report,
        assignment=assignment,
        target_committed_at=target_committed_at,
        host=host,
    )
    if isinstance(applied, Failure):
        return Failure(applied.failure())
    return Success(_ACCEPTED)


def _matched_assignment(
    *, report: FailureReport, host: ManagerHost
) -> Result[tuple[Assignment, str], ManagerError]:
    """The assignment this report names, with its commit time; else `invalid-report`."""
    stored = read_assignment(
        state_dir=host.state_dir,
        consumer_run_id=report.consumer_run_id,
        owner_uid=host.owner_uid,
    )
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    assignment = stored.unwrap()
    if assignment is None:
        return Failure(invalid_report(message="no assignment was issued for that consumer run"))
    if assignment.record_id != report.record_id:
        return Failure(
            invalid_report(message="record_id does not name the credential that run was assigned")
        )
    committed_at = assignment.target_committed_at
    if committed_at is None:
        return Failure(
            invalid_report(message="that run's assignment has not committed a target yet")
        )
    return Success((assignment, committed_at))


def _applied(
    *,
    report: FailureReport,
    assignment: Assignment,
    target_committed_at: str,
    host: ManagerHost,
) -> Result[None, ManagerError]:
    """Validate the interval, compute every effect, then perform them — or perform none."""
    if not occurred_within_interval(
        report=report,
        target_committed_at=target_committed_at,
        lease_closes_at=assignment.lease_expires_at,
        now=host.now,
    ):
        return Failure(
            invalid_report(message="occurred_at is outside that assignment's lease interval")
        )
    records = host.records()
    if isinstance(records, Failure):
        return Failure(records.failure())
    record = _record_for(records=records.unwrap(), record_id=assignment.record_id)
    if record is None:
        return Failure(
            store_unavailable(message="the credential that run was assigned is no longer stored")
        )
    effects = report_effects(
        report=report,
        status=record.status,
        markers=assignment.report_markers,
        generation_matches=record.value_generation == assignment.value_generation,
    )
    if isinstance(effects, Failure):
        return Failure(effects.failure())
    return _performed(
        report=report, assignment=assignment, host=host, record=record, effects=effects.unwrap()
    )


def _record_for(
    *, records: tuple[CredentialRecord, ...], record_id: str
) -> CredentialRecord | None:
    for record in records:
        if record.record_id == record_id:
            return record
    return None


def _performed(
    *,
    report: FailureReport,
    assignment: Assignment,
    host: ManagerHost,
    record: CredentialRecord,
    effects: ReportEffects,
) -> Result[None, ManagerError]:
    """The credential transition first, then the lease, then the marker that records it happened.

        The marker is written LAST on purpose. It is the evidence a replay reads, so writing it
        before the effects it stands for would make a crash in between look -- to the very next
        invocation -- like a report that had already been fully applied.

        THE LEASE RELEASE IS UNCONDITIONAL, and `effects.releases_lease` is deliberately not
        consulted: every row of `_lpm_signal.CLASSIFICATION_HANDLING` sets it, so a guard here would
        be a branch no input can take. A sibling test asserts that invariant directly, so adding a
        classification that does NOT release the lease fails there and sends the next reader to this
        paragraph instead of to a silently wrong release.

    EXACTLY-ONCE IS BY AUTHORITATIVE POSTCONDITION, NOT BY A CHECKPOINT. The contract requires
        each effect to "inspect authoritative state for that position's exact postcondition before
        performing it" so that "an effect commit followed by a crash before `completed_step`
        advancement replay as one logical effect". Each of the three here reconciles against its own
        authoritative state, which is what makes a crash ANYWHERE in this sequence safe to retry --
        including the window a checkpoint record could not cover, between an effect committing
        and its
        checkpoint being written:

        * the credential status, because `_lpm_lifecycle.admitted_move` admits `report` only from
          `valid` and `revalidating`. A credential already moved to `suspect` yields `next_status`
          None on the retry, so the transition cannot be applied twice.
        * the lease, because `release_lease` is conditioned on this run AND this record and answers
          `absent` when there is nothing left to remove.
        * the marker, because `markers_with` is total and `stored_marker` at the top of the command
          answers a fully-applied report as a duplicate.

        A ratified `apply`-phase write-ahead record is still OWED -- it is what orders these effects
        and carries `normalized_close_time` for the `assignment-end-update` this command does
        not yet
        perform. It is not what makes them idempotent.
    """
    if effects.next_status is not None:
        moved = host.write_status(record=record, next_status=effects.next_status, now=host.now)
        if isinstance(moved, Failure):
            return Failure(moved.failure())
    released = _released(assignment=assignment, host=host)
    if isinstance(released, Failure):
        return Failure(released.failure())
    return write_assignment(
        state_dir=host.state_dir,
        assignment=with_marker(assignment=assignment, marker=report_marker(report=report)),
        owner_uid=host.owner_uid,
    )


def _released(*, assignment: Assignment, host: ManagerHost) -> Result[None, ManagerError]:
    path = local_record_path(
        state_dir=host.state_dir,
        family=LEASE_FAMILY,
        identity=[assignment.request.provider, assignment.account_id],
    )
    if isinstance(path, Failure):
        return Failure(path.failure())
    released = release_lease(
        path=path.unwrap(),
        consumer_run_id=assignment.request.consumer_run_id,
        record_id=assignment.record_id,
        owner_uid=host.owner_uid,
    )
    if isinstance(released, Failure):
        return Failure(released.failure())
    return Success(None)
