"""Reconstruct the secret-free selected credential from one retained lease."""

from __future__ import annotations

from collections.abc import Callable

from _lpm_engine_context import SelectedCredential
from _lpm_leases import AccountLease
from _lpm_provision_request import ProvisionRequest
from _lpm_record import CredentialRecord
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import add_seconds

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "recoverable_selection",
    "selected_from_recovery_lease",
]


def recoverable_selection(
    *,
    records: Result[tuple[CredentialRecord, ...], ManagerError],
    lease_for: Callable[[CredentialRecord], Result[AccountLease | None, ManagerError]],
    request: ProvisionRequest,
    lease_started_at: str,
) -> Result[SelectedCredential | None, ManagerError]:
    """Return no selection only when no request-bound lease exists."""
    if isinstance(records, Failure):
        return records
    matches: list[tuple[CredentialRecord, AccountLease]] = []
    for record in records.unwrap():
        if (record.provider, record.kind, record.purpose) != (
            request.provider,
            request.kind,
            request.purpose,
        ):
            continue
        lease = lease_for(record)
        if isinstance(lease, Failure):
            return lease
        held = lease.unwrap()
        if held is not None and _lease_names_request(
            lease=held,
            request=request,
            record=record,
            lease_started_at=lease_started_at,
        ):
            matches.append((record, held))
    if not matches:
        return Success(None)
    if len(matches) != 1:
        return Failure(
            store_unavailable(message="the committed lease selection could not be recovered")
        )
    record, lease = matches[0]
    return selected_from_recovery_lease(record=record, lease=lease)


def selected_from_recovery_lease(
    *, record: CredentialRecord, lease: AccountLease
) -> Result[SelectedCredential, ManagerError]:
    """Rebuild the original metadata-only selection without resolving its value."""
    if record.last_validated is None or record.value_generation is None or record.value_ref is None:
        return Failure(store_unavailable(message="the leased credential metadata is incomplete"))
    return Success(
        SelectedCredential(
            account_id=record.account_id,
            record_id=record.record_id,
            value_generation=record.value_generation,
            value_ref=record.value_ref,
            receipt={
                "record_id": record.record_id,
                "account_id": record.account_id,
                "purpose": record.purpose,
                "validated_at": record.last_validated,
                "lease_expires_at": lease.lease_expires_at,
            },
        )
    )


def _lease_names_request(
    *,
    lease: AccountLease,
    request: ProvisionRequest,
    record: CredentialRecord,
    lease_started_at: str,
) -> bool:
    expected_expiry = add_seconds(timestamp=lease_started_at, seconds=request.lease_seconds)
    return (
        lease.provider == request.provider
        and lease.account_id == record.account_id
        and lease.record_id == record.record_id
        and lease.consumer_run_id == request.consumer_run_id
        and lease.lease_started_at == lease_started_at
        and lease.lease_expires_at == expected_expiry
    )
