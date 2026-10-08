"""The writer role a pending fence may be replayed under, validated against its own owner.

SPECIFICATION/contracts.md requires a fence's "writer role MUST equal the semantic audit actor
assigned to that owning operation, phase and effect by the actor table", fixes
`recovery-writer` for "operation-less lifecycle expiry", and makes "a malformed, unsafe or
relation-invalid fence, including a writer-role mismatch" return `store-unavailable` without
reset or mutation. During global recovery a command "MUST retry only the byte-identical
revision through that role's original entry point, preserving the original semantic audit
actor" — so the role has to be VALIDATED before any retry is issued, not read and trusted.

THE OWNER IS FOUND BY SCANNING, BECAUSE NOTHING INDEXES IT. Write-ahead operation records live
at a path derived from command and idempotency key, while a fence names its owner by
`operation_id`; no derivation goes the other way. So the owning record is identified by reading
the operation family and comparing identifiers, which is also why this module exists apart from
the recovery pass that calls it: resolving an owner is a question about the operation store, not
about the fence traversal.

AN UNPROVEN OWNER IS NOT AN ABSENT OWNER, and collapsing the two is the failure this guards
against. An unsafe or malformed record anywhere in that family means the scan cannot say whether
the fence's owner is there, so the answer is a refusal — which quarantines the record — rather
than "no owner found". The alternative reading would let one damaged neighbour promote a fence to
the operation-less exception and replay it under whatever role it happened to store.

THE POSITION IS SEARCHED RATHER THAN DERIVED, because the contract keys an effect's identity on
its ORDERED POSITION and a phase may repeat an effect name. `fence_owner_defect` re-derives the
effect identifier, actor and writer role for one position from the fence and its owning
operation; a fence belongs to this operation exactly when some position has no defect at all.
Reporting one generic refusal for "no such position" keeps that honest: a fence whose stored role
disagrees with the table and a fence whose effect identifier matches nothing are both fences this
manager must not replay, and neither deserves a message implying the other was ruled out.
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine_context import OperationEngine
from _lpm_fence import MetadataFence
from _lpm_fence_inventory import family_record_files
from _lpm_fence_recovery import fence_owner_defect
from _lpm_localstate import read_local_record
from _lpm_operation import OperationRecord, operation_from_object
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "OWNING_OPERATION_FAMILY",
    "validated_writer_role",
]

OWNING_OPERATION_FAMILY: Final = "operation"


def validated_writer_role(
    *, engine: OperationEngine, fence: MetadataFence
) -> Result[str, ManagerError]:
    """`fence`'s recorded writer role, once its own owner proves that role is the right one.

    An ownerless fence needs no lookup: the fence reader already refuses a null
    `owner_operation_id` in any role but `recovery-writer`, which IS the actor the contract
    assigns operation-less lifecycle expiry, so the relation is settled by validation alone.
    """
    if fence.owner_operation_id is None:
        return Success(fence.writer_role)
    owning = _owning_operation(engine=engine, operation_id=fence.owner_operation_id)
    if isinstance(owning, Failure):
        return Failure(owning.failure())
    return _role_for_an_owned_position(fence=fence, operation=owning.unwrap())


def _owning_operation(
    *, engine: OperationEngine, operation_id: str
) -> Result[OperationRecord, ManagerError]:
    """The write-ahead operation record carrying `operation_id`, or why none can be named."""
    for path in family_record_files(state_dir=engine.state_dir, family=OWNING_OPERATION_FAMILY):
        stored = read_local_record(path=path, owner_uid=engine.owner_uid)
        if isinstance(stored, Failure):
            return Failure(stored.failure())
        # An operation file that vanished under the traversal decodes as `None`, which the
        # validator's own first rule refuses — so a concurrent removal needs no branch of its
        # own and lands in the same unproven-owner refusal as a damaged record.
        parsed = operation_from_object(parsed=stored.unwrap())
        if isinstance(parsed, Failure):
            return Failure(parsed.failure())
        operation = parsed.unwrap()
        if operation.operation_id == operation_id:
            return Success(operation)
    return Failure(
        store_unavailable(
            message="no write-ahead operation record owns this record's pending metadata fence"
        )
    )


def _role_for_an_owned_position(
    *, fence: MetadataFence, operation: OperationRecord
) -> Result[str, ManagerError]:
    """`fence`'s role, if any ordered position of `operation` derives the whole relation."""
    for index in range(len(operation.ordered_effects)):
        if fence_owner_defect(fence=fence, operation=operation, index=index) is None:
            return Success(fence.writer_role)
    return Failure(
        store_unavailable(
            message="no effect position of the owning operation derives this fence's "
            "effect_id and semantic audit actor"
        )
    )
