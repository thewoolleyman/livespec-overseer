"""The assignment record's lifecycle: prepared before the write, promoted after the commit.

SPECIFICATION/contracts.md makes the PREPARED record half of the commit boundary -- "that target
commit plus the durable prepared record makes the assignment successful and consumes the run
identity even if the following `assignment-commit` persistence fails" -- and defines what promotion
changes: "`assignment-commit` MUST record the adapter-supplied target commit time and change
`status` to `committed`".

THE TWO HALVES LIVE TOGETHER BECAUSE THEY SHARE ONE RECORD SHAPE. A prepared assignment must be a
fully conforming assignment record, which means it needs a receipt and a lease close time before the
write that produces the authoritative ones has happened. Promotion then replaces exactly those
fields. Splitting the halves apart would put that one shape's construction in two modules and invite
them to disagree about it.

NEITHER HALF DECIDES ANYTHING. `prepare_assignment` returns the record already on disk unchanged
when one exists, so a resumed provision keeps the account the first attempt chose; the decision
about whether this is a resume belongs to the command.
"""

from __future__ import annotations

from dataclasses import replace

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import (
    COMMITTED_ASSIGNMENT,
    PREPARED_ASSIGNMENT,
    Assignment,
    write_assignment,
)
from _lpm_command_host import ManagerHost
from _lpm_provision import ProvisionReceipt, ProvisionRequest
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError
from _lpm_time import add_seconds

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "lease_close",
    "pending_receipt",
    "prepare_assignment",
    "promote_assignment",
]


def prepare_assignment(
    *,
    request: ProvisionRequest,
    host: ManagerHost,
    record: CredentialRecord,
    prepared: Assignment | None,
) -> Result[Assignment, ManagerError]:
    """The durable prepared record, written BEFORE the target write — or the one already there."""
    if prepared is not None:
        return Success(prepared)
    assignment = Assignment(
        status=PREPARED_ASSIGNMENT,
        request=request,
        target_ref=request.target_ref,
        account_id=record.account_id,
        value_generation=str(record.value_generation),
        value_ref=str(record.value_ref),
        record_id=record.record_id,
        receipt=pending_receipt(record=record, request=request, host=host),
        lease_started_at=host.now,
        lease_expires_at=lease_close(request=request, host=host),
        target_committed_at=None,
        actual_lease_ended_at=None,
        report_markers=(),
        completion=None,
    )
    written = write_assignment(
        state_dir=host.state_dir, assignment=assignment, owner_uid=host.owner_uid
    )
    if isinstance(written, Failure):
        return Failure(written.failure())
    return Success(assignment)


def promote_assignment(
    *, host: ManagerHost, assignment: Assignment, receipt: ProvisionReceipt
) -> Result[None, ManagerError]:
    """Promote the prepared record to `committed`, carrying the receipt the write actually produced.

    The RECEIPT comes from the commit rather than from the prepared record because its
    `validated_at` must be "the `last_validated` of the exact authoritative eligible credential
    reread used to create that prepared assignment" -- a value only the write knows.
    """
    committed = replace(
        assignment,
        status=COMMITTED_ASSIGNMENT,
        receipt=receipt,
        lease_expires_at=receipt.lease_expires_at,
        target_committed_at=host.now,
    )
    return write_assignment(
        state_dir=host.state_dir, assignment=committed, owner_uid=host.owner_uid
    )


def pending_receipt(
    *, record: CredentialRecord, request: ProvisionRequest, host: ManagerHost
) -> ProvisionReceipt:
    """The receipt a PREPARED record carries, superseded by the commit's own before it is answered.

    A prepared assignment must still be a conforming assignment record, and that shape requires a
    receipt. The authoritative one comes from the write; this one exists so the prepared record is
    valid on disk, and `promote_assignment` replaces it with what the commit produced.
    """
    return ProvisionReceipt(
        record_id=record.record_id,
        account_id=record.account_id,
        validated_at=str(record.last_validated or host.now),
        purpose=record.purpose,
        lease_expires_at=lease_close(request=request, host=host),
    )


def lease_close(*, request: ProvisionRequest, host: ManagerHost) -> str:
    """When the lease this request asks for would close, for the prepared record's own shape."""
    return add_seconds(timestamp=host.now, seconds=request.lease_seconds) or host.now
