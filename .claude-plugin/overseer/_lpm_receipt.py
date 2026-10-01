"""The provisioning receipt: the one secret-free answer a committed provision hands back.

SPECIFICATION/contracts.md states the receipt as containing EXACTLY lowercase RFC 4122 UUIDv4
`record_id`, non-empty `account_id` and `purpose`, plus UTC RFC 3339-second `validated_at` and
`lease_expires_at`, and stores it inside the assignment record.

IT IS A CLOSED FIVE-MEMBER SHAPE BECAUSE IT IS THE ONE THING THAT LEAVES THE MANAGER. The
receipt is returned to the consumer and persisted beside the assignment, so "exactly these five"
is the structural reason no credential, login or mailbox byte can ride back out: there is no
member for one to occupy, and the shape is built from the declared list rather than from a
caller's mapping. That is why this lives in its own module rather than as five more checks
inside the assignment validator — it is a record-within-a-record with its own contract sentence,
and it is the one whose membership is load-bearing for secrecy rather than for replay.

`validated_at` MUST equal the `last_validated` of the exact authoritative eligible credential
reread used to create the prepared assignment. That equality is NOT checkable here, because the
reread is gone by the time anything reads the receipt back; it is the create effect's obligation,
asserted where the reread is still in hand. This module validates the receipt's own shape and
says so plainly rather than implying a guarantee it cannot give.
"""

from __future__ import annotations

from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_record import is_uuid4
from _lpm_time import is_canonical_timestamp

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "RECEIPT_MEMBERS",
    "receipt_shape_defect",
]

RECEIPT_MEMBERS: Final = (
    "record_id",
    "account_id",
    "purpose",
    "validated_at",
    "lease_expires_at",
)


def receipt_shape_defect(*, receipt: object) -> str | None:
    """A reason `receipt` is not the exact five-member secret-free receipt."""
    if not isinstance(receipt, dict):
        return "an assignment receipt must be a JSON object"
    source = cast("dict[str, object]", receipt)
    if sorted(source) != sorted(RECEIPT_MEMBERS):
        return f"an assignment receipt must contain exactly {', '.join(RECEIPT_MEMBERS)}"
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return "a receipt record_id must be a lowercase RFC 4122 UUIDv4"
    for member in ("account_id", "purpose"):
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"a receipt {member} must be a non-empty string"
    for member in ("validated_at", "lease_expires_at"):
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"a receipt {member} must be a UTC RFC 3339-second timestamp"
    return None
