"""The `provision` command: resolve the reference, select, lease, write the target, record it.

SPECIFICATION/contracts.md gives `provision` the widest typed-failure set of any consumer
command -- "`provision` MAY emit only `invalid-request`, `retryable-exhaustion`,
`store-unavailable`, `provisioning-failed` or `internal-bug`" -- and `_lpm_provision.provision`
already implements the decision that chooses between them. This module's job is to ASSEMBLE the
context that function needs out of persisted state and the host's ports, and to persist what
the contract says a successful provision leaves behind.

THE AUTHORITATIVE SELECTION IS `provision`'S, NOT THIS MODULE'S -- and this module nonetheless
selects first, which deserves an explanation rather than a reader's suspicion.
`ProvisionContext` takes ONE `lease_path`, and the lease path is keyed by provider and account:
it cannot be known until an account has been chosen. So the account is resolved here, using the
same public `eligible_records` + `select_record` over the same inputs, purely to derive that
path; `provision` then re-runs the identical selection and its answer is the one that governs.
The duplication is deterministic (same records, same observations, same policy, same state) and
it is a consequence of the ratified context shape, not a second policy. A `ProvisionContext`
taking a lease-path FUNCTION would remove it, and that is a change to a ratified module rather
than something to work around silently.

WHAT A SUCCESS PERSISTS, and why both writes come after the receipt. The target commit is the
contract's commit boundary: once it lands the run identity is consumed "even if the following
`assignment-commit` persistence fails". So the assignment record and the selection-state
incumbency are written AFTER `provision` returns a receipt, and a failure of either is reported
as `store-unavailable` rather than retracting a credential that is already in the consumer's
target. Reporting success there would lose the only record a later `report` can be idempotent
against.

THE CONTEXT ASSEMBLY LIVES NEXT DOOR, in `_lpm_provision_context`, and is imported back here. That
module answers "what are we provisioning, with which account, against which lease?"; this one
answers "what does running it change on disk". Keeping them apart is what lets every pre-write
refusal -- an unissued reference, an empty pool, an unreadable lease -- be reasoned about without
the persistence that follows a commit.
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import COMMITTED_ASSIGNMENT, Assignment, write_assignment
from _lpm_command_host import (
    CommandOutcome,
    ManagerHost,
    error_outcome,
    establish_manager_state,
    read_command_object,
    selection_state_path,
    success_outcome,
)
from _lpm_eligibility import SelectionRequest
from _lpm_localstate import write_local_record
from _lpm_provision import (
    ProvisionReceipt,
    ProvisionRequest,
    provision,
    provision_request_from_object,
    receipt_object,
)
from _lpm_provision_context import provision_context, provision_issuance
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, invalid_request
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
    """Validate, resolve, select, lease, commit the target, then record the assignment."""
    parsed = read_command_object(source=source, read_input=host.read_input, refuse=invalid_request)
    if isinstance(parsed, Failure):
        return error_outcome(error=parsed.failure())
    request = provision_request_from_object(parsed=parsed.unwrap())
    if isinstance(request, Failure):
        return error_outcome(error=request.failure())
    provisioned = _provisioned(request=request.unwrap(), host=host)
    if isinstance(provisioned, Failure):
        return error_outcome(error=provisioned.failure())
    return success_outcome(
        payload={
            "operation": PROVISION_OPERATION,
            "receipt": receipt_object(receipt=provisioned.unwrap()),
        }
    )


def _provisioned(
    *, request: ProvisionRequest, host: ManagerHost
) -> Result[ProvisionReceipt, ManagerError]:
    issuance = provision_issuance(target_ref=request.target_ref, host=host)
    if isinstance(issuance, Failure):
        return Failure(issuance.failure())
    records = host.records()
    if isinstance(records, Failure):
        return Failure(records.failure())
    held = records.unwrap()
    prepared = provision_context(
        request=request, host=host, issuance=issuance.unwrap(), records=held
    )
    if isinstance(prepared, Failure):
        return Failure(prepared.failure())
    context, selected = prepared.unwrap()
    established = establish_manager_state(state_dir=host.state_dir, owner_uid=host.owner_uid)
    if isinstance(established, Failure):
        return Failure(established.failure())
    receipt = provision(request=request, context=context)
    if isinstance(receipt, Failure):
        return Failure(receipt.failure())
    return _recorded(
        request=request,
        host=host,
        record=selected,
        receipt=receipt.unwrap(),
        state=context.state,
    )


def _recorded(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    record: CredentialRecord,
    receipt: ProvisionReceipt,
    state: SelectionState,
) -> Result[ProvisionReceipt, ManagerError]:
    """Persist the assignment and the selection incumbency the committed target now implies.

    The selection state is the one `_context` already read rather than a fresh read: this runs
    after the target commit, and re-reading would let a concurrent writer's state silently
    replace the one the selection that just committed was actually decided against.
    """
    assignment = Assignment(
        status=COMMITTED_ASSIGNMENT,
        request=request,
        target_ref=request.target_ref,
        account_id=record.account_id,
        value_generation=str(record.value_generation),
        value_ref=str(record.value_ref),
        record_id=record.record_id,
        receipt=receipt,
        lease_started_at=host.now,
        lease_expires_at=receipt.lease_expires_at,
        target_committed_at=host.now,
        actual_lease_ended_at=None,
        report_markers=(),
        completion=None,
    )
    written = write_assignment(
        state_dir=host.state_dir, assignment=assignment, owner_uid=host.owner_uid
    )
    if isinstance(written, Failure):
        return Failure(written.failure())
    committed = _committed_selection(request=request, host=host, record=record, state=state)
    if isinstance(committed, Failure):
        return Failure(committed.failure())
    return Success(receipt)


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
