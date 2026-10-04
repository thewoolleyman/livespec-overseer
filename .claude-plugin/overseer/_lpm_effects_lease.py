"""The `lease-release` executor, shared by provision `cleanup` and every closing phase.

SPECIFICATION/contracts.md requires that "`lease-release` MUST be a completed no-op when no
matching live lease remains" and that provision `cleanup` "MUST always end with `lease-release`
whenever any `start` effect committed; that release is a completed no-op when no matching lease
remains, so cleanup is never empty". One executor serves both, because the question is the same
one in both places: is THIS run's lease on THIS record still standing?

RELEASING IS NEVER UNCONDITIONAL. `release_lease` compares both the run and the record before
unlinking, so a lease a DIFFERENT run has since taken on the same account is left exactly as
found. That distinction is why the underlying surface answers with three closed words rather
than a Boolean: `absent` says there was nothing to release and `foreign` says somebody else's
lease is standing — and collapsing them would let a late cleanup report that it released a
lease it had actually skipped.

BOTH NON-RELEASING ANSWERS ARE `satisfied`, AND THAT IS NOT A SHORTCUT. The contract defines a
completed no-op for exactly these cases: this run holds no live lease on this record either
way, which IS the position's postcondition. Reporting `performed` for them would claim work
that did not happen, and refusing would wedge a cleanup that is doing precisely what it was
asked to do.

WHERE THE BINDING COMES FROM DEPENDS ON WHAT STILL EXISTS, and the order is deliberate. In a
closing phase the assignment is still on disk — `assignment-close` is the LAST effect of those
arrays — so its own stored request and binding name the provider, account and record
authoritatively, which matters because `report`, `complete`, `release` and `expire` inputs do
NOT carry a provider. In provision `cleanup` the preceding `prepared-assignment-discard` has
already removed the assignment, so the selection this phase was composed with is the only
remaining source. Asking the assignment FIRST means a close never depends on an input it was
not given, and `cleanup` never depends on a record it just deleted.
"""

from __future__ import annotations

from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment, assignment_from_object
from _lpm_engine_context import EffectContext, input_text, required_input
from _lpm_engine_records import record_path, stored_record
from _lpm_leases import LEASE_RELEASED, release_lease
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "LeaseKey",
    "lease_release",
    "leased_binding",
]


@dataclass(frozen=True, kw_only=True)
class LeaseKey:
    """Everything `release_lease` compares: whose lease, on which account and record."""

    consumer_run_id: str
    provider: str
    account_id: str
    record_id: str


def leased_binding(*, context: EffectContext) -> Result[LeaseKey, ManagerError]:
    """The run, provider, account and credential record this lease is keyed on.

    The run id is carried OUT rather than re-read by the caller. Re-reading it would add a
    second refusal path that the first read has already made unreachable, and an unreachable
    refusal is indistinguishable from an untested one.
    """
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    found = stored_record(context=context, family="assignment", identity=(run_id.unwrap(),))
    if isinstance(found, Failure):
        return Failure(found.failure())
    stored = found.unwrap()
    if stored is None:
        return _binding_from_inputs(context=context, run_id=run_id.unwrap())
    assignment = assignment_from_object(parsed=stored)
    if isinstance(assignment, Failure):
        return assignment
    return Success(_binding_from_assignment(assignment=assignment.unwrap(), run_id=run_id.unwrap()))


def lease_release(*, context: EffectContext) -> Result[str, ManagerError]:
    """Release this run's lease on its bound record, or settle an already-absent one."""
    binding = leased_binding(context=context)
    if isinstance(binding, Failure):
        return binding
    key = binding.unwrap()
    released = release_lease(
        path=record_path(
            state_dir=context.engine.state_dir,
            family="lease",
            identity=(key.provider, key.account_id),
        ),
        consumer_run_id=key.consumer_run_id,
        record_id=key.record_id,
        owner_uid=context.engine.owner_uid,
    )
    if isinstance(released, Failure):
        return Failure(released.failure())
    return Success(PERFORMED if released.unwrap() == LEASE_RELEASED else SATISFIED)


def _binding_from_assignment(*, assignment: Assignment, run_id: str) -> LeaseKey:
    # A stored assignment's `request` was validated as a complete `provision` normalized
    # input on the way out of `assignment_from_object`, so `provider` is present and is a
    # non-empty string by construction; a guard here would be unreachable rather than safe.
    return LeaseKey(
        consumer_run_id=run_id,
        provider=str(assignment.request["provider"]),
        account_id=assignment.account_id,
        record_id=assignment.record_id,
    )


def _binding_from_inputs(*, context: EffectContext, run_id: str) -> Result[LeaseKey, ManagerError]:
    provider = input_text(operation=context.operation, member="provider")
    if isinstance(provider, Failure):
        return provider
    inputs = required_input(value=context.inputs.provision, member="provision inputs")
    if isinstance(inputs, Failure):
        return inputs
    selected = inputs.unwrap().selected
    return Success(
        LeaseKey(
            consumer_run_id=run_id,
            provider=provider.unwrap(),
            account_id=selected.account_id,
            record_id=selected.record_id,
        )
    )
