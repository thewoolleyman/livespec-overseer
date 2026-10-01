"""The `provision` command: prepare durably, commit the target, then promote — and replay safely.

SPECIFICATION/contracts.md names the commit boundary precisely, and the whole shape of this module
follows from one sentence of it: "that target commit plus the durable prepared record makes the
assignment successful and consumes the run identity even if the following `assignment-commit`
persistence fails". Two consequences, both load-bearing.

THE PREPARED ASSIGNMENT IS WRITTEN BEFORE THE TARGET WRITE, NOT AFTER IT. An earlier cut of this
module wrote the assignment after the receipt came back and called the result atomic. It was not:
a crash between the target commit and that write left NO durable record that the run had been
assigned anything, so an identical retry selected again -- possibly a different account -- and
wrote a second credential into a destination that already held a committed one, consuming the run
identity twice and leaving two accounts leased to one run. The prepared record is what lets a
retry know that it IS a retry.

A RESUMED PROVISION NEVER SELECTS AGAIN. Recovery reads the account, generation and value
reference out of the prepared assignment and hands them to `provision_selected`, which performs no
selection of its own. Re-selecting would be the same defect wearing a write-ahead record: the
first attempt's target write may already have committed, and only the account it chose may be
used.

THE WRITE-AHEAD OPERATION RECORD CARRIES WHAT THE ASSIGNMENT CANNOT. The prepared assignment says
"this run is assigned this credential"; the operation record says which EFFECTS have committed, so
a resumed attempt skips the selection state it already advanced instead of repeating it. Its
removal is what commits the operation as complete.

EVERYTHING HAPPENS UNDER PER-RUN SERIALIZATION, which the contract requires first of any command
carrying a `consumer_run_id`. Without it two concurrent invocations of the same run would both
read the same prepared assignment and both resume it.

A DIFFERENT REQUEST FOR A CONSUMED RUN IS REFUSED. The run identity is consumed by the request
that prepared it, so a second, non-identical request naming the same run is `invalid-request`
rather than a silent re-provision -- "when applied to provisioning requests, `identical`, `same
logical request` and `exact request` mean field-for-field equality of normalized provisioning
requests".
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import COMMITTED_ASSIGNMENT, Assignment, read_assignment
from _lpm_assignment_lifecycle import prepare_assignment, promote_assignment
from _lpm_command_host import (
    CommandOutcome,
    ManagerHost,
    error_outcome,
    read_command_object,
    run_serialization,
    selection_state_path,
    success_outcome,
)
from _lpm_eligibility import SelectionRequest
from _lpm_localstate import write_local_record
from _lpm_locks import release_lock
from _lpm_provision import (
    ProvisionContext,
    ProvisionReceipt,
    ProvisionRequest,
    provision_request_from_object,
    provision_selected,
    receipt_object,
)
from _lpm_provision_context import provision_context, provision_issuance
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, internal_bug, invalid_request
from _lpm_selection_state import SelectionState, selection_state_object
from _lpm_strategy import committed_selection_state

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "PROVISION_OPERATION",
    "run_provision_command",
]

PROVISION_OPERATION: Final = "provision"


def run_provision_command(*, source: str, host: ManagerHost) -> CommandOutcome:
    """Validate, serialize on the run, then provision or resume exactly once."""
    parsed = read_command_object(source=source, read_input=host.read_input, refuse=invalid_request)
    if isinstance(parsed, Failure):
        return error_outcome(error=parsed.failure())
    decoded = provision_request_from_object(parsed=parsed.unwrap())
    if isinstance(decoded, Failure):
        return error_outcome(error=decoded.failure())
    request = decoded.unwrap()
    held = run_serialization(host=host, consumer_run_id=request.consumer_run_id)
    if isinstance(held, Failure):
        return error_outcome(error=held.failure())
    try:
        provisioned = _serialized(request=request, host=host)
    finally:
        release_lock(held=held.unwrap())
    if isinstance(provisioned, Failure):
        return error_outcome(error=provisioned.failure())
    return success_outcome(
        payload={
            "operation": PROVISION_OPERATION,
            "receipt": receipt_object(receipt=provisioned.unwrap()),
        }
    )


def _serialized(
    *, request: ProvisionRequest, host: ManagerHost
) -> Result[ProvisionReceipt, ManagerError]:
    """Replay a consumed run, resume a prepared one, or run a fresh provision — in that order."""
    existing = read_assignment(
        state_dir=host.state_dir,
        consumer_run_id=request.consumer_run_id,
        owner_uid=host.owner_uid,
    )
    if isinstance(existing, Failure):
        return Failure(existing.failure())
    assignment = existing.unwrap()
    if assignment is not None and assignment.request != request:
        return Failure(
            invalid_request(message="that consumer run is already assigned a different request")
        )
    if assignment is not None and assignment.status == COMMITTED_ASSIGNMENT:
        # The whole operation already committed: an idempotent replay answers the SAME receipt and
        # touches nothing. Selecting or writing here is the defect this branch exists to prevent.
        return Success(assignment.receipt)
    return _carried(request=request, host=host, prepared=assignment)


def _carried(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    prepared: Assignment | None,
) -> Result[ProvisionReceipt, ManagerError]:
    """Assemble the context, then choose the record: the selection's, or the prepared record's."""
    issuance = provision_issuance(target_ref=request.target_ref, host=host)
    if isinstance(issuance, Failure):
        return Failure(issuance.failure())
    records = host.records()
    if isinstance(records, Failure):
        return Failure(records.failure())
    held = records.unwrap()
    context = provision_context(
        request=request,
        host=host,
        issuance=issuance.unwrap(),
        records=held,
        prepared=prepared,
    )
    if isinstance(context, Failure):
        return Failure(context.failure())
    assembled, selected = context.unwrap()
    if selected is None:
        return Failure(
            internal_bug(message="the credential a prepared assignment names is no longer stored")
        )
    return _committed(
        request=request,
        host=host,
        context=assembled,
        record=selected,
        prepared=prepared,
    )


def _committed(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    context: ProvisionContext,
    record: CredentialRecord,
    prepared: Assignment | None,
) -> Result[ProvisionReceipt, ManagerError]:
    """Prepare durably, commit the target, promote, then advance the selection incumbency."""
    opened = prepare_assignment(request=request, host=host, record=record, prepared=prepared)
    if isinstance(opened, Failure):
        return Failure(opened.failure())
    receipt = provision_selected(request=request, context=context, record=record)
    if isinstance(receipt, Failure):
        return Failure(receipt.failure())
    promoted = promote_assignment(host=host, assignment=opened.unwrap(), receipt=receipt.unwrap())
    if isinstance(promoted, Failure):
        return Failure(promoted.failure())
    advanced = _committed_selection(request=request, host=host, record=record, state=context.state)
    if isinstance(advanced, Failure):
        return Failure(advanced.failure())
    return Success(receipt.unwrap())


def _committed_selection(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    record: CredentialRecord,
    state: SelectionState,
) -> Result[None, ManagerError]:
    updated = committed_selection_state(
        state=state,
        strategy=request.strategy,
        request=SelectionRequest(
            provider=request.provider, kind=request.kind, purpose=request.purpose
        ),
        record_id=record.record_id,
        target_committed_at=host.now,
    )
    if isinstance(updated, Failure):
        return Failure(updated.failure())
    return write_local_record(
        path=selection_state_path(state_dir=host.state_dir),
        value=selection_state_object(state=updated.unwrap()),
        owner_uid=host.owner_uid,
    )
