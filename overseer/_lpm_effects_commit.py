"""`target-write` and `assignment-commit`: placing the credential and fixing its instant.

SPECIFICATION/contracts.md orders these two across a PHASE BOUNDARY. `target-write` is the
last effect of provision `start`; `assignment-commit`, which "MUST record the adapter-supplied
target commit time and change `status` to `committed`", is the first of `postcommit`, and
`start` reaches `postcommit` only "after a committed target". So one of them learns the commit
instant from the adapter and the other — possibly in a different process after a crash — has
to find it again.

THE POSTCONDITION IS A RECORD THIS OPERATION WROTE, NEVER AN OBSERVATION OF THE WORLD. The
destination's BYTES cannot answer "did THIS operation's write commit?", because a
byte-identical value could have been placed there by the previous generation and because
reading a credential back is not a commit acknowledgement. The authoritative answer is the
target-commit record naming this reference, run, record and generation — see
`_lpm_target_commit` — so a replay settles the position rather than writing a credential twice,
and `assignment-commit` reads the instant back instead of re-sampling a clock.

THE ADAPTER'S THREE STATUSES MEAN THREE DIFFERENT THINGS AND ARE KEPT APART. `in-progress`
says a timed-out or orphaned sibling may still own the reference lock and still be writing, so
the destination's state is unknowable and this is `store-unavailable`; `uncommitted` says the
prior bytes definitively survive, which is the pre-commit failure that routes `start` to
`cleanup`; `committed` is the only one that may persist an instant.

A COMMITTED ASSIGNMENT AT A DIFFERENT INSTANT IS A BUG, NOT A REWRITE. Two disagreeing commit
times for one reference means this engine's own phase reasoning is wrong, and overwriting
either would silently move a window the lease, the rollout-start minimum and every later close
time are all measured against.
"""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import (
    COMMITTED_STATUS,
    Assignment,
    assignment_from_object,
    assignment_object,
)
from _lpm_engine_context import (
    EffectContext,
    ProvisionInputs,
    input_text,
    required_input,
    settle,
)
from _lpm_engine_records import (
    RecordAction,
    record_path,
    satisfied_action,
    settle_record,
    stored_record,
    write_action,
)
from _lpm_localstate import write_local_record
from _lpm_results import ManagerError, internal_bug, provisioning_failed, store_unavailable
from _lpm_target import COMMITTED, IN_PROGRESS, commit_credential
from _lpm_target_commit import TargetCommit, target_commit_from_object, target_commit_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "assignment_commit",
    "target_write",
]


def target_write(*, context: EffectContext) -> Result[str, ManagerError]:
    """Place the credential at the destination once, and persist the commit instant.

    The adapter's three statuses are kept apart because the contract gives them different
    meanings: `in-progress` says a timed-out or orphaned sibling may still own the reference
    lock and still be writing, so the destination's state is unknowable and this is
    `store-unavailable`; `uncommitted` says the prior bytes definitively survive, which is
    the pre-commit failure that routes `start` to `cleanup`.
    """
    prepared = _commit_preconditions(context=context)
    if isinstance(prepared, Failure):
        return prepared
    inputs, target_ref, assignment = prepared.unwrap()
    found = stored_record(context=context, family="target-commit", identity=(target_ref,))
    if isinstance(found, Failure):
        return Failure(found.failure())
    return settle(
        satisfied=found.unwrap() is not None,
        perform=lambda: _committed_write(
            context=context, inputs=inputs, target_ref=target_ref, assignment=assignment
        ),
    )


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


def _commit_preconditions(
    *, context: EffectContext
) -> Result[tuple[ProvisionInputs, str, Assignment], ManagerError]:
    inputs = required_input(value=context.inputs.provision, member="provision inputs")
    if isinstance(inputs, Failure):
        return inputs
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    found = stored_record(context=context, family="assignment", identity=(run_id.unwrap(),))
    if isinstance(found, Failure):
        return Failure(found.failure())
    stored = found.unwrap()
    if stored is None:
        return Failure(
            store_unavailable(message="no prepared assignment stands for this target write")
        )
    assignment = assignment_from_object(parsed=stored)
    if isinstance(assignment, Failure):
        return assignment
    return Success((inputs.unwrap(), assignment.unwrap().target_ref, assignment.unwrap()))


def _committed_write(
    *,
    context: EffectContext,
    inputs: ProvisionInputs,
    target_ref: str,
    assignment: Assignment,
) -> Result[None, ManagerError]:
    outcome = commit_credential(
        destination=inputs.destination,
        value=inputs.credential_value,
        owner_uid=context.engine.owner_uid,
        fence_now=inputs.fence_now,
        lease_expires_at=assignment.lease_expires_at,
        lock=inputs.lock,
    )
    if outcome.status == IN_PROGRESS:
        return Failure(store_unavailable(message="another writer still owns this target reference"))
    if outcome.status != COMMITTED or outcome.committed_at is None:
        return Failure(
            provisioning_failed(message="the target write did not commit; the prior bytes stand")
        )
    commit = TargetCommit(
        target_ref=target_ref,
        consumer_run_id=str(assignment.request["consumer_run_id"]),
        record_id=assignment.record_id,
        value_generation=assignment.value_generation,
        committed_at=outcome.committed_at,
    )
    return write_local_record(
        path=record_path(
            state_dir=context.engine.state_dir, family="target-commit", identity=(target_ref,)
        ),
        value=target_commit_object(commit=commit),
        owner_uid=context.engine.owner_uid,
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
    return target_commit_from_object(parsed=stored)


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
