"""Commit a prepared assignment from durable target replacement evidence."""

from __future__ import annotations

from _lpm_assignment import (
    COMMITTED_STATUS,
    Assignment,
    assignment_from_object,
    assignment_object,
)
from _lpm_effect_target_records import decoded_target_commit
from _lpm_engine_context import EffectContext, input_text
from _lpm_engine_records import (
    RecordAction,
    satisfied_action,
    settle_record,
    stored_record,
    write_action,
)
from _lpm_results import ManagerError, internal_bug, store_unavailable
from _lpm_target_commit import TargetCommit

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "assignment_commit",
]


def assignment_commit(*, context: EffectContext) -> Result[str, ManagerError]:
    """Record the adapter-supplied commit time and change `status` to `committed`."""
    located = _commit_record(context=context)
    if isinstance(located, Failure):
        return located
    commit = located.unwrap()
    return settle_record(
        context=context,
        family="assignment",
        identity=(commit.consumer_run_id,),
        decide=lambda stored: _commit_decision(stored=stored, commit=commit),
    )


def _commit_record(*, context: EffectContext) -> Result[TargetCommit, ManagerError]:
    target_ref = input_text(operation=context.operation, member="target_ref")
    if isinstance(target_ref, Failure):
        return target_ref
    found = stored_record(context=context, family="target-commit", identity=(target_ref.unwrap(),))
    if isinstance(found, Failure):
        return Failure(found.failure())
    stored = found.unwrap()
    if stored is None:
        return Failure(
            store_unavailable(message="no committed target write stands for this assignment")
        )
    return decoded_target_commit(context=context, stored=stored)


def _commit_decision(
    *, stored: object | None, commit: TargetCommit
) -> Result[RecordAction, ManagerError]:
    if stored is None:
        return Failure(
            store_unavailable(message="no assignment stands for this post-commit update")
        )
    assignment = assignment_from_object(parsed=stored)
    if isinstance(assignment, Failure):
        return assignment
    current = assignment.unwrap()
    if current.status == COMMITTED_STATUS:
        return _already_committed(current=current, commit=commit)
    committed = Assignment(
        status=COMMITTED_STATUS,
        request=current.request,
        target_ref=current.target_ref,
        account_id=current.account_id,
        value_generation=current.value_generation,
        value_ref=current.value_ref,
        record_id=current.record_id,
        receipt=current.receipt,
        lease_started_at=current.lease_started_at,
        lease_expires_at=current.lease_expires_at,
        target_committed_at=commit.committed_at,
        actual_lease_ended_at=current.actual_lease_ended_at,
        report_markers=current.report_markers,
        completion=current.completion,
    )
    return Success(write_action(value=assignment_object(assignment=committed)))


def _already_committed(
    *, current: Assignment, commit: TargetCommit
) -> Result[RecordAction, ManagerError]:
    if current.target_committed_at != commit.committed_at:
        return Failure(
            internal_bug(
                message="this assignment is committed at a different adapter-supplied instant"
            )
        )
    return Success(satisfied_action())
