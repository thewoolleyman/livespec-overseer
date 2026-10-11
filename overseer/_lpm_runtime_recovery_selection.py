"""Reconstruct the secret-free selected credential from one retained lease."""

from __future__ import annotations

from typing import cast

from _lpm_engine_context import SelectedCredential
from _lpm_leases import AccountLease
from _lpm_record import CredentialRecord

__all__: list[str] = [
    "selected_from_recovery_lease",
]


def selected_from_recovery_lease(
    *, record: CredentialRecord, lease: AccountLease
) -> SelectedCredential:
    """Rebuild the original metadata-only selection without resolving its value."""
    return SelectedCredential(
        account_id=record.account_id,
        record_id=record.record_id,
        value_generation=cast("str", record.value_generation),
        value_ref=cast("str", record.value_ref),
        receipt={
            "record_id": record.record_id,
            "account_id": record.account_id,
            "purpose": record.purpose,
            "validated_at": cast("str", record.last_validated),
            "lease_expires_at": lease.lease_expires_at,
        },
    )
