"""The provisioning command boundary: one request in, one secret-free receipt out.

SPECIFICATION/contracts.md fixes the success answer as a receipt carrying `record_id`, `account_id`,
the authoritative `validated_at`, `purpose` and `lease_expires_at` — AND NO SECRET BYTES. It
requires a pre-commit failure to release any acquired lease, leave the target byte-identical
and leave `consumer_run_id` unconsumed, returning exactly one typed `retryable-exhaustion`,
`invalid-request`, `store-unavailable` or `provisioning-failed`.

THE RECEIPT IS FIVE MEMBERS, NOT FOUR. This item's acceptance line names record identity,
account identity, validation time and purpose; the ratified contract names those four plus
`lease_expires_at`, and `SPECIFICATION/` governs. The fifth member is not extra information
leaking out — it is the instant after which the consumer MUST stop using what it was just
handed, so a receipt without it tells a consumer to use a credential and not when to stop.
The acceptance line's real content, that nothing beyond secret-free identity crosses this
boundary, is what `receipt_object` enforces.

THE EXACT REQUEST OBJECT AND ITS NORMALIZATION LIVE NEXT DOOR, in
`_lpm_provision_request`, and are imported back here. That module answers "are these the
same logical request?"; this one answers "what does running that request do to the world".
Keeping them apart is what lets the replay, tombstone-reuse and pending-operation refusals
share one definition of request identity instead of each spelling it out.

THIS MODULE NEVER TOUCHES A CREDENTIAL VALUE, AND THE INJECTION IS WHY. `read_value` is a
port: the caller resolves the authoritative `value_ref` to raw bytes and this boundary hands
those bytes straight to the target adapter. spec.md forbids the manager from proxying,
relaying or rewriting inference traffic or entering the inference request path, and a
boundary that fetched values itself would be one refactor away from also using one.

THE LEASE IS RELEASED ON EVERY FAILING PATH THAT TOOK IT, AND ONLY THOSE. Release is
conditioned on this run AND this record by the lease module, so a release racing a later
run's lease cannot delete it. A release that itself fails is reported as `store-unavailable`
rather than swallowed, because the honest answer then is that a lease may still stand and a
later retry or its expiry must resolve it — exactly what the contract requires.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_eligibility import (
    AccountObservation,
    EligibilityPolicy,
    SelectionRequest,
    eligible_records,
)
from _lpm_leases import AccountLease, acquire_lease, new_lease, release_lease
from _lpm_provision_request import (
    PROVISION_OPTIONAL_MEMBERS,
    PROVISION_REQUIRED_MEMBERS,
    PROVISION_VERSION,
    ProvisionRequest,
    provision_request_from_object,
    provision_request_object,
)
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, internal_bug, provisioning_failed, retryable_exhaustion
from _lpm_selection_state import SelectionState
from _lpm_strategy import select_record
from _lpm_target import (
    COMMITTED,
    IN_PROGRESS,
    TargetIssuance,
    TargetLock,
    commit_credential,
    resolve_issuance,
)

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "PROVISION_OPTIONAL_MEMBERS",
    "PROVISION_REQUIRED_MEMBERS",
    "PROVISION_VERSION",
    "RECEIPT_MEMBERS",
    "CredentialValueReader",
    "ProvisionContext",
    "ProvisionReceipt",
    "ProvisionRequest",
    "provision",
    "provision_request_from_object",
    "provision_request_object",
    "receipt_object",
]

RECEIPT_MEMBERS: Final = (
    "record_id",
    "account_id",
    "validated_at",
    "purpose",
    "lease_expires_at",
)


@dataclass(frozen=True, kw_only=True)
class ProvisionReceipt:
    """The secret-free answer to a successful provision."""

    record_id: str
    account_id: str
    validated_at: str
    purpose: str
    lease_expires_at: str


class CredentialValueReader(Protocol):
    """The injected port that resolves an authoritative `value_ref` to raw bytes."""

    def __call__(self, *, value_ref: str) -> Result[bytes, ManagerError]:
        """The still-current credential bytes for `value_ref`, or a typed failure."""
        ...


@dataclass(frozen=True, kw_only=True)
class ProvisionContext:
    """Everything the boundary needs that is not the request itself."""

    records: tuple[CredentialRecord, ...]
    state: SelectionState
    issuance: TargetIssuance
    issuance_bound: bool
    observations: Mapping[str, AccountObservation]
    policy: EligibilityPolicy
    lease_path: Path
    target_lock: TargetLock
    owner_uid: int
    now: str
    read_value: CredentialValueReader


def receipt_object(*, receipt: ProvisionReceipt) -> dict[str, object]:
    """The receipt as exactly its declared members — nothing else can ride along."""
    return {member: getattr(receipt, member) for member in RECEIPT_MEMBERS}


def provision(
    *, request: ProvisionRequest, context: ProvisionContext
) -> Result[ProvisionReceipt, ManagerError]:
    """Select one validated credential and atomically write only it to the isolated target."""
    destination = resolve_issuance(
        issuance=context.issuance,
        target_ref=request.target_ref,
        consumer_run_id=request.consumer_run_id,
        now=context.now,
        bound=context.issuance_bound,
    )
    if isinstance(destination, Failure):
        return Failure(destination.failure())
    selected = _selected(request=request, context=context)
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    return _leased_commit(
        request=request, context=context, record=selected.unwrap(), destination=destination.unwrap()
    )


def _selected(
    *, request: ProvisionRequest, context: ProvisionContext
) -> Result[CredentialRecord, ManagerError]:
    selection = SelectionRequest(
        provider=request.provider, kind=request.kind, purpose=request.purpose
    )
    eligible = eligible_records(
        request=selection,
        records=context.records,
        observations=context.observations,
        policy=context.policy,
    )
    return select_record(
        strategy=request.strategy,
        request=selection,
        records=eligible,
        state=context.state,
    )


def _leased_commit(
    *,
    request: ProvisionRequest,
    context: ProvisionContext,
    record: CredentialRecord,
    destination: str,
) -> Result[ProvisionReceipt, ManagerError]:
    lease = new_lease(
        provider=record.provider,
        account_id=record.account_id,
        record_id=record.record_id,
        consumer_run_id=request.consumer_run_id,
        now=context.now,
        lease_seconds=request.lease_seconds,
    )
    if isinstance(lease, Failure):
        return Failure(lease.failure())
    taken = acquire_lease(
        path=context.lease_path, lease=lease.unwrap(), owner_uid=context.owner_uid, now=context.now
    )
    if isinstance(taken, Failure):
        return Failure(taken.failure())
    held = taken.unwrap()
    written = _write_target(context=context, record=record, destination=destination, lease=held)
    if isinstance(written, Failure):
        return _released(context=context, record=record, held=held, failure=written.failure())
    return Success(
        ProvisionReceipt(
            record_id=record.record_id,
            account_id=record.account_id,
            validated_at=written.unwrap(),
            purpose=record.purpose,
            lease_expires_at=held.lease_expires_at,
        )
    )


def _write_target(
    *,
    context: ProvisionContext,
    record: CredentialRecord,
    destination: str,
    lease: AccountLease,
) -> Result[str, ManagerError]:
    """Resolve the selected record's value and commit it, answering with `validated_at`.

    The authoritative validation time is read from the record the write actually used, so
    a receipt can never report a freshness the provisioned credential does not have.
    """
    if record.value_ref is None or record.last_validated is None:
        return Failure(internal_bug(message="a selected record carries a value and a validation"))
    value = context.read_value(value_ref=record.value_ref)
    if isinstance(value, Failure):
        return Failure(value.failure())
    status = commit_credential(
        destination=destination,
        value=value.unwrap(),
        owner_uid=context.owner_uid,
        fence_now=context.now,
        lease_expires_at=lease.lease_expires_at,
        lock=context.target_lock,
    ).status
    if status == COMMITTED:
        return Success(record.last_validated)
    if status == IN_PROGRESS:
        return Failure(retryable_exhaustion(message="the target write is still in progress"))
    return Failure(provisioning_failed(message="the target adapter did not commit the credential"))


def _released(
    *,
    context: ProvisionContext,
    record: CredentialRecord,
    held: AccountLease,
    failure: ManagerError,
) -> Result[ProvisionReceipt, ManagerError]:
    released = release_lease(
        path=context.lease_path,
        consumer_run_id=held.consumer_run_id,
        record_id=record.record_id,
        owner_uid=context.owner_uid,
    )
    if isinstance(released, Failure):
        return Failure(released.failure())
    return Failure(failure)
