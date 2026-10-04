"""The two executors of a `target` command's `issue` phase.

SPECIFICATION/contracts.md states the array exactly: "Target `issue` MUST contain exactly
`issuance-create`, `registration-remove`." Both act on manager-local state only, and both
are written so that re-entering the phase at a stale checkpoint settles rather than repeats.

THE ISSUANCE IS CREATED, NEVER REPLACED. An existing record at the same reference whose bytes
DIFFER belongs to another issuance of that reference, so it is reported `store-unavailable`
and left exactly as found — the contract's no-reset rule applied to the one record a later
provision resolves its destination through. Only a byte-identical record counts as this
position's satisfied postcondition.

THE REGISTRATION REMOVAL IS IDEMPOTENT BY DEFINITION. The contract defines absence after a
delete effect's required predecessor as the committed postcondition, which is what lets the
unlink's own crash window be survived by simply asking again.

`issued_at` COMES FROM THE OPERATION'S `accepted_at`. A fresh clock read here would move the
issuance's expiry on every replay, so a crash-recovered issue would expire at a different
instant than the one it first committed — and the byte comparison above, which is what makes
the replay settle at all, would never match again.
"""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine_context import EffectContext, input_text, required_input
from _lpm_engine_records import (
    RecordAction,
    remove_action,
    satisfied_action,
    settle_record,
    write_action,
)
from _lpm_results import ManagerError, store_unavailable
from _lpm_target import TargetIssuance, issuance_object, new_issuance

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "issuance_create",
    "planned_issuance",
    "registration_remove",
]


def planned_issuance(*, context: EffectContext) -> Result[TargetIssuance, ManagerError]:
    """The one issuance this `issue` phase is authorized to commit.

    Built from the operation's own stored input and `accepted_at`, so every replay of the
    phase plans a BYTE-IDENTICAL record and the stored-bytes comparison below is meaningful.
    """
    inputs = required_input(value=context.inputs.target, member="target inputs")
    if isinstance(inputs, Failure):
        return inputs
    target = inputs.unwrap()
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    return new_issuance(
        reference=target.reference,
        consumer_run_id=run_id.unwrap(),
        adapter=target.adapter,
        destination=target.destination,
        now=context.operation.accepted_at,
    )


def issuance_create(*, context: EffectContext) -> Result[str, ManagerError]:
    """Commit this phase's issuance, or settle an already-committed byte-identical one."""
    planned = planned_issuance(context=context)
    if isinstance(planned, Failure):
        return planned
    issuance = planned.unwrap()
    desired = issuance_object(issuance=issuance)
    return settle_record(
        context=context,
        family="issuance",
        identity=(issuance.reference,),
        decide=lambda stored: _issuance_decision(stored=stored, desired=desired),
    )


def registration_remove(*, context: EffectContext) -> Result[str, ManagerError]:
    """Remove this run's registration, or settle an already-absent one."""
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    return settle_record(
        context=context,
        family="run-registration",
        identity=(run_id.unwrap(),),
        decide=lambda stored: Success(satisfied_action() if stored is None else remove_action()),
    )


def _issuance_decision(
    *, stored: object | None, desired: dict[str, object]
) -> Result[RecordAction, ManagerError]:
    if stored is None:
        return Success(write_action(value=desired))
    if stored != desired:
        return Failure(
            store_unavailable(message="a different issuance already holds this target reference")
        )
    return Success(satisfied_action())
