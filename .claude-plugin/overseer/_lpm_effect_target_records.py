"""Interpret legacy and atomic target records at the provision phase boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, Literal, TypeVar, cast

from _lpm_assignment import Assignment
from _lpm_engine_context import EffectContext, required_input
from _lpm_engine_records import stored_record
from _lpm_results import ManagerError, store_unavailable
from _lpm_target import COMMITTED
from _lpm_target_commit import TargetCommit, target_commit_from_object
from _lpm_target_evidence import TargetEvidence, target_evidence_from_object

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "TARGET_RECORD_ABSENT",
    "TARGET_RECORD_COMMITTED",
    "TARGET_RECORD_PENDING",
    "TARGET_RECORD_SATISFIED",
    "TargetRecordState",
    "decoded_target_commit",
    "fold_manager_result",
    "persisted_port_commit",
    "target_commit_from_evidence",
    "target_write_state",
]

_Input = TypeVar("_Input")
_Output = TypeVar("_Output")
TargetRecordState = Literal["absent", "committed", "pending", "satisfied"]
TARGET_RECORD_ABSENT: Final[TargetRecordState] = "absent"
TARGET_RECORD_COMMITTED: Final[TargetRecordState] = "committed"
TARGET_RECORD_PENDING: Final[TargetRecordState] = "pending"
TARGET_RECORD_SATISFIED: Final[TargetRecordState] = "satisfied"


def fold_manager_result(
    *,
    result: Result[_Input, ManagerError],
    success: Callable[[_Input], Result[_Output, ManagerError]],
    failure: Callable[[ManagerError], Result[_Output, ManagerError]],
) -> Result[_Output, ManagerError]:
    """Fold either Result rail while retaining its concrete error type."""
    if isinstance(result, Failure):
        return failure(result.failure())
    return success(result.unwrap())


def target_commit_from_evidence(
    *, evidence: TargetEvidence, record_id: str
) -> Result[TargetCommit, ManagerError]:
    """Adapt committed atomic-replacement evidence to the operation's commit view."""
    committed = evidence.status == COMMITTED and evidence.committed_at is not None
    results: dict[bool, Result[TargetCommit, ManagerError]] = {
        False: Failure(store_unavailable(message="target evidence is not committed")),
        True: Success(
            TargetCommit(
                target_ref=evidence.target_ref,
                consumer_run_id=evidence.consumer_run_id,
                record_id=record_id,
                value_generation=evidence.value_generation,
                committed_at=cast("str", evidence.committed_at),
            )
        ),
    }
    return results[committed]


def decoded_target_commit(
    *, context: EffectContext, stored: object
) -> Result[TargetCommit, ManagerError]:
    """Decode either retained legacy commit evidence or exact atomic-replace evidence."""
    return fold_manager_result(
        result=target_commit_from_object(parsed=stored),
        success=lambda commit: Success(commit),
        failure=lambda _error: fold_manager_result(
            result=required_input(value=context.inputs.provision, member="provision inputs"),
            success=lambda inputs: fold_manager_result(
                result=target_evidence_from_object(parsed=stored),
                success=lambda evidence: target_commit_from_evidence(
                    evidence=evidence,
                    record_id=inputs.selected.record_id,
                ),
                failure=lambda error: Failure(error),
            ),
            failure=lambda error: Failure(error),
        ),
    )


def target_write_state(
    *, stored: object | None, target_ref: str, assignment: Assignment
) -> Result[TargetRecordState, ManagerError]:
    """Whether target-write is satisfied or must query the isolated target status role."""
    if stored is None:
        return Success(TARGET_RECORD_PENDING)
    legacy = target_commit_from_object(parsed=stored)
    if isinstance(legacy, Success):
        commit = legacy.unwrap()
        matches = (
            commit.target_ref,
            commit.consumer_run_id,
            commit.record_id,
            commit.value_generation,
        ) == (
            target_ref,
            str(assignment.request["consumer_run_id"]),
            assignment.record_id,
            assignment.value_generation,
        )
        results: dict[bool, Result[TargetRecordState, ManagerError]] = {
            False: Failure(store_unavailable(message="target commit names another binding")),
            True: Success(TARGET_RECORD_SATISFIED),
        }
        return results[matches]
    return fold_manager_result(
        result=target_evidence_from_object(parsed=stored),
        success=lambda atomic: _matched_target_evidence(
            atomic=atomic,
            target_ref=target_ref,
            assignment=assignment,
        ),
        failure=lambda error: Failure(error),
    )


def _matched_target_evidence(
    *, atomic: TargetEvidence, target_ref: str, assignment: Assignment
) -> Result[TargetRecordState, ManagerError]:
    matches = (
        atomic.target_ref,
        atomic.consumer_run_id,
        atomic.value_generation,
    ) == (
        target_ref,
        str(assignment.request["consumer_run_id"]),
        assignment.value_generation,
    )
    results: dict[bool, Result[TargetRecordState, ManagerError]] = {
        False: Failure(store_unavailable(message="target evidence names another binding")),
        True: Success(TARGET_RECORD_PENDING),
    }
    return results[matches]


def persisted_port_commit(
    *, context: EffectContext, target_ref: str, assignment: Assignment
) -> Result[TargetRecordState, ManagerError]:
    """Validate the exact evidence a successful isolated target role left behind."""
    return fold_manager_result(
        result=stored_record(context=context, family="target-commit", identity=(target_ref,)),
        success=lambda stored: _persisted_record(
            stored=stored,
            target_ref=target_ref,
            assignment=assignment,
        ),
        failure=lambda error: Failure(error),
    )


def _persisted_record(
    *, stored: object | None, target_ref: str, assignment: Assignment
) -> Result[TargetRecordState, ManagerError]:
    if stored is None:
        return Success(TARGET_RECORD_ABSENT)
    return fold_manager_result(
        result=target_evidence_from_object(parsed=stored),
        success=lambda evidence: fold_manager_result(
            result=target_commit_from_evidence(evidence=evidence, record_id=assignment.record_id),
            success=lambda commit: _matched_persisted_commit(
                commit=commit,
                target_ref=target_ref,
                assignment=assignment,
            ),
            failure=lambda error: Failure(error),
        ),
        failure=lambda error: Failure(error),
    )


def _matched_persisted_commit(
    *, commit: TargetCommit, target_ref: str, assignment: Assignment
) -> Result[TargetRecordState, ManagerError]:
    matches = (
        commit.target_ref,
        commit.consumer_run_id,
        commit.value_generation,
    ) == (
        target_ref,
        str(assignment.request["consumer_run_id"]),
        assignment.value_generation,
    )
    results: dict[bool, Result[TargetRecordState, ManagerError]] = {
        False: Failure(store_unavailable(message="target evidence names another binding")),
        True: Success(TARGET_RECORD_COMMITTED),
    }
    return results[matches]
