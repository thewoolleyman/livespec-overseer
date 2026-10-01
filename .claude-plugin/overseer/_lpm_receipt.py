"""The stored side of the provisioning receipt: validating the five members back off disk.

`_lpm_provision` owns the receipt's TYPE and its encoding (`ProvisionReceipt`,
`receipt_object`); this module owns the inverse, which only a reader of persisted manager
state needs. SPECIFICATION/contracts.md states the shape where it defines the assignment
record that carries one: "`receipt` MUST contain exactly lowercase RFC 4122 UUIDv4
`record_id`, non-empty `account_id` and `purpose`, plus UTC RFC 3339-second `validated_at`
and `lease_expires_at`".

IT IS A SEPARATE MODULE BECAUSE IT IS A SEPARATE RECORD, not to shed lines. The receipt is
the one secret-free object that crosses the consumer boundary, and it is embedded in both the
assignment record and the tombstone the contract defines — so a decoder living inside either
one would have to be reached from the other, which for a private helper is exactly the
cross-module private import pyright-strict and `check-private-calls` both reject.

A DEFECT IS `store-unavailable`, NOT `invalid-request`. Every caller here is reading state the
MANAGER wrote. A receipt that does not conform was not produced by `receipt_object`, so the
honest report is that this manager's own state cannot be used — never that the consumer's
request was wrong.
"""

from __future__ import annotations

from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_provision import ProvisionReceipt
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "RECEIPT_NON_EMPTY_MEMBERS",
    "RECEIPT_STORED_MEMBERS",
    "RECEIPT_TIMESTAMPS",
    "receipt_from_object",
]

RECEIPT_STORED_MEMBERS: Final = (
    "record_id",
    "account_id",
    "validated_at",
    "purpose",
    "lease_expires_at",
)

RECEIPT_NON_EMPTY_MEMBERS: Final = ("account_id", "purpose")
RECEIPT_TIMESTAMPS: Final = ("validated_at", "lease_expires_at")


def receipt_from_object(*, parsed: object) -> Result[ProvisionReceipt, ManagerError]:
    """Validate one stored receipt; anything nonconforming is `store-unavailable`."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="a stored receipt must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    defect = _receipt_defect(source=source)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    return Success(
        ProvisionReceipt(
            record_id=str(source["record_id"]),
            account_id=str(source["account_id"]),
            validated_at=str(source["validated_at"]),
            purpose=str(source["purpose"]),
            lease_expires_at=str(source["lease_expires_at"]),
        )
    )


def _receipt_defect(*, source: dict[str, object]) -> str | None:
    if sorted(source) != sorted(RECEIPT_STORED_MEMBERS):
        return f"a stored receipt carries exactly {', '.join(RECEIPT_STORED_MEMBERS)}"
    for member in RECEIPT_NON_EMPTY_MEMBERS:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"receipt {member} must be a non-empty string"
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return "receipt record_id must be a lowercase RFC 4122 UUIDv4"
    for member in RECEIPT_TIMESTAMPS:
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"receipt {member} must be a UTC RFC 3339-second timestamp"
    return None
