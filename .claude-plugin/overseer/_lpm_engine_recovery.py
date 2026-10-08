"""Mandatory global recovery: reconcile every pending metadata fence this manager holds.

SPECIFICATION/contracts.md requires mandatory global recovery to "attempt pending fences in
lexical `record_id` order", and to reconcile an existing fence before any later conditional set
for that record may create another revision. A record whose fence cannot be reconciled is
QUARANTINED for the current invocation, its fence and owning safety state retained.

THE REREAD IS THE ONLY THING THAT MAY REMOVE A FENCE. "An exact desired next revision carrying
that effect_id proves the logical effect committed and MUST advance it without another adapter
call", so a fence whose revision is already authoritative is settled on the reread alone and only
then removed. A pass that issued the create first would reach the same chain — byte-identical
physical duplicates collapse — while making a call the contract forbids, which is why the ORDER
rather than the outcome is the rule.

THE REFUSAL CHANNEL IS RESERVED FOR A TRAVERSAL THAT COULD NOT BE BOUNDED. A fence file no record
identity resolves to supplies no bound at all, and skipping it would let a command proceed against
a record whose pending effect nobody looked at. Everything a single record's OWN fence can go wrong
with quarantines that record and leaves the pass itself successful, because that bound is the whole
point: an unreconcilable fence must not wedge records it has nothing to do with.

THIS PASS NEVER WRITES AN OPERATION RECORD. The terminal-success pending-fence sequence — which
rewrites an owning operation directly to its failure `recovery` phase once the fenced revision
becomes authoritative — is a SEPARATE contract rule and is not reached from here; a reader should
not take a green pass as evidence that it ran. What this pass guarantees about an owning operation
is only that it leaves it exactly as found.

THE QUARANTINE IS ONLY A BOUND UNTIL SOMETHING ASKS IT, which is what the two admission entry
points are for. "A requested command MUST return `store-unavailable` when its explicit or resolved
record identity is quarantined" and "Provision MUST exclude a quarantined record", so each kind of
request has one seam: an identity-dependent command asks about the record it is bound to, and
selection asks which of its matching candidates survive. Each runs the pass itself rather than
taking a quarantine set from its caller, because the set is a property of the fences on disk right
now and a command that supplied its own would be enforcing nothing.

A PASS THAT COULD NOT BE BOUNDED ADMITS NOTHING. A fence file no record identity resolves to makes
the whole pass refuse, and neither seam may substitute an empty quarantine set for that refusal:
proceeding would let the command touch a record whose pending effect nobody looked at, which is
the one outcome the traversal's own refusal channel exists to prevent.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine_context import OperationEngine
from _lpm_fence import MetadataFence, fence_from_object
from _lpm_fence_inventory import pending_fence_records
from _lpm_fence_owner import validated_writer_role
from _lpm_fence_recovery import (
    DESIRED_REVISION,
    GlobalRecovery,
    quarantine_refusal,
    recover_pending_fences,
    selectable_candidates,
)
from _lpm_fence_reread import apply_fenced_set, authoritative_reread
from _lpm_fence_store import fence_path, resolve_fence
from _lpm_localstate import read_local_record
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "admitted_record_identity",
    "admitted_selection",
    "recover_metadata_fences",
]


def recover_metadata_fences(*, engine: OperationEngine) -> Result[GlobalRecovery, ManagerError]:
    """Attempt every pending metadata-effect fence on disk, in lexical `record_id` order.

    Every fence is attempted, however many of them fail. A record whose own fence cannot be
    reconciled is quarantined and the traversal carries on, because that bound is the whole
    point: an unreconcilable fence must not wedge records it has nothing to do with.
    """
    records = pending_fence_records(state_dir=engine.state_dir)
    if isinstance(records, Failure):
        return Failure(records.failure())
    return Success(
        recover_pending_fences(
            record_ids=records.unwrap(),
            # `recover_pending_fences` calls this POSITIONALLY, which its own published
            # callable type fixes, so it is supplied as a lambda rather than as a nested
            # definition carrying a positional parameter of its own.
            reconcile=lambda record_id: _attempted(engine=engine, record_id=record_id),
        )
    )


def admitted_record_identity(
    *, engine: OperationEngine, record_id: str
) -> Result[str, ManagerError]:
    """`record_id`, once a global recovery pass proves no quarantine covers it.

    This is the seam an identity-dependent command asks, whether its record identity was given
    explicitly or resolved on the way in. A command whose result has no dependency on any
    quarantined record is admitted and proceeds normally, which is the bound working rather
    than a leniency.
    """
    recovered = recover_metadata_fences(engine=engine)
    if isinstance(recovered, Failure):
        return Failure(recovered.failure())
    refusal = quarantine_refusal(record_id=record_id, quarantined=recovered.unwrap().quarantined)
    if refusal is not None:
        return Failure(refusal)
    return Success(record_id)


def admitted_selection(
    *, engine: OperationEngine, matching: Sequence[str]
) -> Result[tuple[str, ...], ManagerError]:
    """The candidates selection may still choose from, after this pass's quarantines.

    `matching` is already narrowed to the requested provider, kind and purpose; what this adds
    is the one exclusion a caller cannot derive for itself, together with the refusal an
    emptied pool earns. A pool emptied BY quarantine is never reported as exhaustion.
    """
    recovered = recover_metadata_fences(engine=engine)
    if isinstance(recovered, Failure):
        return Failure(recovered.failure())
    return selectable_candidates(matching=matching, quarantined=recovered.unwrap().quarantined)


def _attempted(*, engine: OperationEngine, record_id: str) -> Result[None, ManagerError]:
    """Reconcile one record's pending fence, or report why it must be quarantined."""
    path = _fence_file(engine=engine, record_id=record_id)
    stored = read_local_record(path=path, owner_uid=engine.owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    # An ABSENT fence decodes as `None` and is refused by the validator's own first rule, so a
    # fence resolved out from under this traversal needs no separate branch: it quarantines a
    # record nothing can mutate anyway, which is the conservative direction.
    validated = fence_from_object(parsed=stored.unwrap())
    if isinstance(validated, Failure):
        return Failure(validated.failure())
    return _settled(engine=engine, fence=validated.unwrap(), path=path)


def _settled(
    *, engine: OperationEngine, fence: MetadataFence, path: Path
) -> Result[None, ManagerError]:
    """Decide `fence` against the authoritative chain, retrying only its own revision."""
    if authoritative_reread(store=engine.store, fence=fence) == DESIRED_REVISION:
        return resolve_fence(path=path, owner_uid=engine.owner_uid)
    replay = validated_writer_role(engine=engine, fence=fence)
    if isinstance(replay, Failure):
        return Failure(replay.failure())
    return _retried(engine=engine, fence=fence, path=path, writer_role=replay.unwrap())


def _retried(
    *, engine: OperationEngine, fence: MetadataFence, path: Path, writer_role: str
) -> Result[None, ManagerError]:
    """Issue the one revision `fence` records, as the role its own owner authorized.

    A RECOVERY PASS ALWAYS INHERITS ITS FENCE, so the retry is made with
    `created_from_absence` false, always. "Every call that found the fence already present MUST
    conservatively treat it as having a prior unknown outcome": this pass did not create any of
    these fences and cannot distinguish a crash before the original adapter call from one after
    it, so a later definitive `condition-failed` or `uncommitted` RETAINS the fence here rather
    than resolving it.
    """
    # `apply_fenced_set` refuses only an unencodable record or a classification outside its own
    # closed sets; this fence's records came back through `fence_from_object` a moment ago and
    # both classifications are computed in there, so neither refusal is reachable.
    decision = apply_fenced_set(
        store=engine.store, fence=fence, created_from_absence=False
    ).unwrap()
    if decision.retain_fence:
        return Failure(
            store_unavailable(
                message=f"this record's {writer_role} retry resolved to {decision.disposition}"
            )
        )
    return resolve_fence(path=path, owner_uid=engine.owner_uid)


def _fence_file(*, engine: OperationEngine, record_id: str) -> Path:
    # The fence family and its single-value identity come from the contract's own local path
    # table, so this lookup has no refusal to report; an unwrap failure would be a defect in
    # that table rather than an operator-visible condition.
    return fence_path(state_dir=engine.state_dir, record_id=record_id).unwrap()
