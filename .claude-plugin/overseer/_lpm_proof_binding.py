"""Resolve the retained assignment or closing record a proof contribution is bound to."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import COMMITTED_STATUS, Assignment, assignment_from_object
from _lpm_closing_records import ClosingRecord, closing_record
from _lpm_engine_context import EffectContext, input_text
from _lpm_engine_records import stored_record
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "proof_binding",
]


def proof_binding(*, context: EffectContext) -> Result[Assignment | ClosingRecord, ManagerError]:
    """The committed provision binding or authoritative closing binding for this effect."""
    if context.operation.command != "provision":
        return _closing_binding(context=context)
    return _provision_binding(context=context)


def _closing_binding(*, context: EffectContext) -> Result[ClosingRecord, ManagerError]:
    bound = closing_record(context=context)
    if isinstance(bound, Failure):
        return bound
    if context.operation.command != "complete":
        return bound
    existing = bound.unwrap().completion
    incoming = context.operation.normalized_input
    if existing is not None and existing != incoming:
        return Failure(store_unavailable(message="a different completion already closes this run"))
    return bound


def _provision_binding(*, context: EffectContext) -> Result[Assignment, ManagerError]:
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    found = stored_record(context=context, family="assignment", identity=(run_id.unwrap(),))
    if isinstance(found, Failure):
        return found
    if found.unwrap() is None:
        return Failure(store_unavailable(message="no assignment stands for this merge effect"))
    parsed = assignment_from_object(parsed=found.unwrap())
    if isinstance(parsed, Failure):
        return parsed
    assignment = parsed.unwrap()
    if assignment.status != COMMITTED_STATUS or assignment.target_committed_at is None:
        return Failure(
            store_unavailable(message="a merge effect contributes only a committed assignment")
        )
    return Success(assignment)
