"""`tombstone-create` and `assignment-close`: the tombstone-first end of every closing phase.

SPECIFICATION/contracts.md fixes both the order and the reason: "Tombstone creation MUST commit
before assignment removal; while both files survive that crash window, the tombstone is
authoritative and reuse remains refused." The scenario "Tombstone-first close survives an
assignment-removal crash" then states the recovery: "the retry removes the redundant assignment
without losing report, completion or target-binding evidence".

THE ORDER IS ENFORCED HERE, NOT MERELY IMPLIED BY THE ARRAY. `assignment-close` reads the
tombstone and REFUSES while none stands, so a phase driven out of order — or a replay whose
checkpoint rewound past the creation — cannot remove the live assignment first. The two failure
directions are not symmetric: a crash with both files present leaves a closed binding readable
twice, while a crash with neither leaves a `consumer_run_id` that looks unconsumed and could be
provisioned again.

EVERY TOMBSTONE MEMBER IS COPIED FROM THE ASSIGNMENT, so the planned record is a function of
stored state alone and a replay plans byte-identical content. That is what makes "a different
tombstone already closes this run" a genuine refusal rather than a replay artefact: two
different tombstones for one run mean two commands disagree about when that run's lease ended.

AN ASSIGNMENT THAT IS ALREADY GONE SETTLES RATHER THAN REFUSING, because `closing_record`
reaching the TOMBSTONE is exactly the evidence the creation committed — the contract defines
absence after a delete effect's required predecessor as the committed postcondition, and this is
that rule applied one position earlier.
"""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import assignment_from_object
from _lpm_assignment_close import close_times
from _lpm_closing_records import (
    ASSIGNMENT_FAMILY,
    TOMBSTONE_FAMILY,
    closing_record,
)
from _lpm_engine_context import EffectContext
from _lpm_engine_records import (
    RecordAction,
    remove_action,
    satisfied_action,
    settle_record,
    stored_record,
    write_action,
)
from _lpm_results import ManagerError, store_unavailable
from _lpm_tombstone import tombstone_from_assignment, tombstone_object

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "assignment_close",
    "tombstone_create",
]


def tombstone_create(*, context: EffectContext) -> Result[str, ManagerError]:
    """Commit this run's tombstone from its live assignment, or settle the one standing."""
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    run_id = bound.unwrap().consumer_run_id
    planned = _planned_tombstone(context=context, consumer_run_id=run_id)
    if isinstance(planned, Failure):
        return Failure(planned.failure())
    return settle_record(
        context=context,
        family=TOMBSTONE_FAMILY,
        identity=(run_id,),
        decide=lambda held: _tombstone_decision(held=held, planned=planned.unwrap()),
    )


def assignment_close(*, context: EffectContext) -> Result[str, ManagerError]:
    """Remove the live assignment, but only once its tombstone is durably authoritative."""
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    record = bound.unwrap()
    if record.family != TOMBSTONE_FAMILY:
        return Failure(
            store_unavailable(
                message="the tombstone must commit before this run's assignment is removed"
            )
        )
    return settle_record(
        context=context,
        family=ASSIGNMENT_FAMILY,
        identity=(record.consumer_run_id,),
        decide=lambda held: Success(satisfied_action() if held is None else remove_action()),
    )


def _planned_tombstone(
    *, context: EffectContext, consumer_run_id: str
) -> Result[dict[str, object] | None, ManagerError]:
    """The tombstone this close derives from the live assignment, or None when it is gone."""
    found = stored_record(context=context, family=ASSIGNMENT_FAMILY, identity=(consumer_run_id,))
    if isinstance(found, Failure):
        return Failure(found.failure())
    held = found.unwrap()
    if held is None:
        return Success(None)
    assignment = assignment_from_object(parsed=held)
    if isinstance(assignment, Failure):
        return Failure(assignment.failure())
    live = assignment.unwrap()
    times = close_times(
        command=context.operation.command,
        lease_started_at=live.lease_started_at,
        lease_expires_at=live.lease_expires_at,
        target_committed_at=live.target_committed_at,
        accepted_at=context.operation.accepted_at,
    )
    if isinstance(times, Failure):
        return Failure(times.failure())
    closed = tombstone_from_assignment(assignment=live, close_times=times.unwrap())
    if isinstance(closed, Failure):
        return Failure(closed.failure())
    return Success(tombstone_object(tombstone=closed.unwrap()))


def _tombstone_decision(
    *, held: object | None, planned: dict[str, object] | None
) -> Result[RecordAction, ManagerError]:
    if planned is None:
        # The assignment is gone, so `closing_record` resolved the TOMBSTONE and it stands.
        return Success(satisfied_action())
    if held is None:
        return Success(write_action(value=planned))
    if held != planned:
        return Failure(store_unavailable(message="a different tombstone already closes this run"))
    return Success(satisfied_action())
