"""Claiming, reading and resolving one record's pending metadata-effect fence.

SPECIFICATION/contracts.md requires that, under the credential-record lock and BEFORE the
adapter's physical-create call, every conditional-set atomically CREATE this file from absence
or find it BYTE-IDENTICAL; a different existing fence is `store-unavailable`. It further
requires that every call which found the fence ALREADY PRESENT conservatively treat it as
having a prior unknown outcome — including after a crash between fence creation and the first
adapter call.

THAT "CREATED FROM ABSENCE OR FOUND PRESENT" BIT IS NOT BOOKKEEPING; IT IS THE WHOLE
DISCRIMINATOR. An existing fence cannot distinguish a crash BEFORE the adapter call from a
crash AFTER it, so the two cases are collapsed into the conservative one and the claim carries
that fact forward to the reconciliation. A caller that lost it would be free to treat a
definitive `condition-failed` from its own first call as proof the condition failed, when an
earlier attempt it knows nothing about may already have committed the revision.

IDENTITY IS COMPARED ON THE STORED BYTES, not on two parsed objects. The retry is permitted to
issue only the byte-identical revision title and fields, so the comparison that authorizes it
has to be a byte comparison — and a stored fence that is malformed is, by that comparison,
simply not the one being claimed, which is the same `store-unavailable` the contract gives a
malformed fence anyway. `read_fence` is the surface that reports WHY a stored fence is
unusable, and mandatory global recovery uses that one.

REMOVAL IS NARROW BY DESIGN. The contract removes a fence in exactly two situations — a
definitive first-call result that THIS invocation's absence-create earned, and an authoritative
desired revision — and retains it on every unknown outcome. So this module offers
`resolve_fence` for the removal and no general-purpose delete; deciding WHICH of those
situations holds belongs to the reconciliation, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_text
from _lpm_fence import MetadataFence, fence_from_object, fence_object
from _lpm_localstate import (
    read_local_record,
    read_local_text,
    remove_local_record,
    write_local_text,
)
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, internal_bug, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "FenceClaim",
    "claim_fence",
    "fence_path",
    "read_fence",
    "resolve_fence",
]


@dataclass(frozen=True, kw_only=True)
class FenceClaim:
    """One claim on a record's fence, and whether THIS invocation created it from absence.

    `created_from_absence` is false for a fence that was already there, which the contract
    requires every such caller to treat as evidence of a prior UNKNOWN outcome.
    """

    fence: MetadataFence
    created_from_absence: bool


def fence_path(*, state_dir: Path, record_id: str) -> Result[Path, ManagerError]:
    """The deterministic owner-only path of `record_id`'s pending metadata-effect fence."""
    return local_record_path(
        state_dir=state_dir, family="pending-metadata-effect", identity=(record_id,)
    )


def read_fence(*, path: Path, owner_uid: int) -> Result[MetadataFence | None, ManagerError]:
    """Read and validate one fence; absence MEANS there is no pending metadata create."""
    stored = read_local_record(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return stored
    parsed = stored.unwrap()
    if parsed is None:
        return Success(None)
    return fence_from_object(parsed=parsed)


def claim_fence(
    *, path: Path, fence: MetadataFence, owner_uid: int
) -> Result[FenceClaim, ManagerError]:
    """Create `fence` from absence, or accept a byte-identical one already present.

    A DIFFERENT existing fence is `store-unavailable` and is left exactly as found: it belongs
    to another pending effect on the same record, and overwriting it would release the guard
    that stops that effect's late duplicate from outranking a later revision.
    """
    encoded = canonical_json_text(value=fence_object(fence=fence))
    if isinstance(encoded, Failure):
        return Failure(internal_bug(message="a metadata fence is not canonical-JSON encodable"))
    expected = encoded.unwrap()
    stored = read_local_text(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return stored
    present = stored.unwrap()
    if present is None:
        written = write_local_text(path=path, text=expected, owner_uid=owner_uid)
        if isinstance(written, Failure):
            return written
        return Success(FenceClaim(fence=fence, created_from_absence=True))
    if present != expected:
        return Failure(
            store_unavailable(
                message="a different pending metadata-effect fence already guards this record"
            )
        )
    return Success(FenceClaim(fence=fence, created_from_absence=False))


def resolve_fence(*, path: Path, owner_uid: int) -> Result[None, ManagerError]:
    """Remove a fence whose effect the reconciliation proved resolved.

    Idempotent, because the removal sits in its own crash window: the contract treats absence
    after the authorizing step as the committed postcondition rather than as an error.
    """
    return remove_local_record(path=path, owner_uid=owner_uid)
