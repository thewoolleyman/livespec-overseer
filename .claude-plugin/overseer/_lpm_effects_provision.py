"""The executors that take a run's lease and stand up — or discard — its prepared assignment.

SPECIFICATION/contracts.md states the arrays exactly: "Provision `start` MUST contain exactly
`lease-create`, `prepared-assignment-create`, `target-write`" and "`cleanup` MUST contain
`prepared-assignment-discard` when prepared state exists and MUST always end with
`lease-release` whenever any `start` effect committed". The two effects that establish prepared
state and the one that retracts it live here; the target commit that sits between them is a
different concern and lives in `_lpm_effects_commit`.

EVERY TIME COMES FROM THE RECORD, NEVER FROM A CLOCK HERE. The lease window is anchored on the
operation's retained `accepted_at`, so a replay plans a BYTE-IDENTICAL lease and the
stored-bytes comparison settles instead of taking the account again under a new window.

A LIVE FOREIGN LEASE IS `retryable-exhaustion`, NOT A FAILURE OF THIS OPERATION. The account
belongs to another in-flight run until its lease lapses; asking again later is the defined
remedy, and overwriting it would hand two runs the same account. An EXPIRED lease IS replaced,
which is what lets an account recover from a crashed consumer with no cooperation from it.

`prepared-assignment-discard` REFUSES A COMMITTED ASSIGNMENT. `cleanup` is reached only after a
PRE-COMMIT failure, so a committed assignment standing here is evidence the engine's own phase
reasoning is wrong — and removing it would destroy a live binding a consumer is already using.
Absence is the committed postcondition, exactly as for every other delete effect.
"""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import (
    COMMITTED_STATUS,
    PREPARED_STATUS,
    Assignment,
    assignment_from_object,
    assignment_object,
)
from _lpm_engine_context import EffectContext, input_integer, input_text, required_input
from _lpm_engine_records import (
    RecordAction,
    record_path,
    remove_action,
    satisfied_action,
    settle_record,
    write_action,
)
from _lpm_leases import (
    AccountLease,
    lease_from_object,
    lease_is_live,
    lease_object,
    new_lease,
    read_lease,
)
from _lpm_results import ManagerError, retryable_exhaustion, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "lease_create",
    "prepared_assignment_create",
    "prepared_assignment_discard",
]


def lease_create(*, context: EffectContext) -> Result[str, ManagerError]:
    """Take this run's lease on the selected account, or settle the one it already holds."""
    planned = _planned_lease(context=context)
    if isinstance(planned, Failure):
        return planned
    lease = planned.unwrap()
    desired = lease_object(lease=lease)
    return settle_record(
        context=context,
        family="lease",
        identity=(lease.provider, lease.account_id),
        decide=lambda stored: _lease_decision(
            stored=stored, desired=desired, now=context.operation.accepted_at
        ),
    )


def prepared_assignment_create(*, context: EffectContext) -> Result[str, ManagerError]:
    """Create this run's PREPARED assignment, or settle an assignment already standing."""
    planned = _planned_assignment(context=context)
    if isinstance(planned, Failure):
        return planned
    assignment = planned.unwrap()
    desired = assignment_object(assignment=assignment)
    run_id = str(assignment.request["consumer_run_id"])
    return settle_record(
        context=context,
        family="assignment",
        identity=(run_id,),
        decide=lambda stored: Success(
            write_action(value=desired) if stored is None else satisfied_action()
        ),
    )


def prepared_assignment_discard(*, context: EffectContext) -> Result[str, ManagerError]:
    """Remove an UNCOMMITTED assignment; absence settles, and a committed one refuses."""
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    return settle_record(
        context=context,
        family="assignment",
        identity=(run_id.unwrap(),),
        decide=lambda stored: _discard_decision(stored=stored),
    )


def _planned_lease(*, context: EffectContext) -> Result[AccountLease, ManagerError]:
    inputs = required_input(value=context.inputs.provision, member="provision inputs")
    if isinstance(inputs, Failure):
        return inputs
    selected = inputs.unwrap().selected
    provider = input_text(operation=context.operation, member="provider")
    if isinstance(provider, Failure):
        return provider
    seconds = input_integer(operation=context.operation, member="lease_seconds")
    if isinstance(seconds, Failure):
        return seconds
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    return new_lease(
        provider=provider.unwrap(),
        account_id=selected.account_id,
        record_id=selected.record_id,
        consumer_run_id=run_id.unwrap(),
        now=context.operation.accepted_at,
        lease_seconds=seconds.unwrap(),
    )


def _lease_decision(
    *, stored: object | None, desired: dict[str, object], now: str
) -> Result[RecordAction, ManagerError]:
    if stored is None:
        return Success(write_action(value=desired))
    if stored == desired:
        return Success(satisfied_action())
    parsed = lease_from_object(parsed=stored)
    if isinstance(parsed, Failure):
        return parsed
    standing = parsed.unwrap()
    if lease_is_live(lease=standing, now=now):
        return Failure(
            retryable_exhaustion(
                message=(
                    "the selected account is leased to another run until "
                    f"{standing.lease_expires_at}"
                )
            )
        )
    return Success(write_action(value=desired))


def _planned_assignment(*, context: EffectContext) -> Result[Assignment, ManagerError]:
    inputs = required_input(value=context.inputs.provision, member="provision inputs")
    if isinstance(inputs, Failure):
        return inputs
    selected = inputs.unwrap().selected
    target_ref = input_text(operation=context.operation, member="target_ref")
    if isinstance(target_ref, Failure):
        return target_ref
    held = _held_lease(context=context, selected_account=selected.account_id)
    if isinstance(held, Failure):
        return held
    lease = held.unwrap()
    return Success(
        Assignment(
            status=PREPARED_STATUS,
            request=dict(context.operation.normalized_input),
            target_ref=target_ref.unwrap(),
            account_id=selected.account_id,
            value_generation=selected.value_generation,
            value_ref=selected.value_ref,
            record_id=selected.record_id,
            receipt=selected.receipt,
            lease_started_at=lease.lease_started_at,
            lease_expires_at=lease.lease_expires_at,
            target_committed_at=None,
            actual_lease_ended_at=None,
            report_markers=(),
            completion=None,
        )
    )


def _held_lease(
    *, context: EffectContext, selected_account: str
) -> Result[AccountLease, ManagerError]:
    provider = input_text(operation=context.operation, member="provider")
    if isinstance(provider, Failure):
        return provider
    stored = read_lease(
        path=record_path(
            state_dir=context.engine.state_dir,
            family="lease",
            identity=(provider.unwrap(), selected_account),
        ),
        owner_uid=context.engine.owner_uid,
    )
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    lease = stored.unwrap()
    if lease is None:
        return Failure(
            store_unavailable(message="this phase's lease-create left no lease to bind against")
        )
    return Success(lease)


def _discard_decision(*, stored: object | None) -> Result[RecordAction, ManagerError]:
    if stored is None:
        return Success(satisfied_action())
    assignment = assignment_from_object(parsed=stored)
    if isinstance(assignment, Failure):
        return assignment
    if assignment.unwrap().status == COMMITTED_STATUS:
        return Failure(
            store_unavailable(message="a committed assignment is never discarded by cleanup")
        )
    return Success(remove_action())
