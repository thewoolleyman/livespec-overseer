"""The serialized runtime executor for every coexistence-proof contribution.

All commands share one proof record, so the named proof lock covers the complete authoritative
read, event merge and atomic replacement.  A replay derives its contribution only from retained
operation and binding evidence; it never samples wall time and never carries a stale proof
snapshot across the lock boundary.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment
from _lpm_closing_records import ClosingRecord
from _lpm_engine_context import EffectContext
from _lpm_localstate import write_local_record
from _lpm_locks import release_lock, take_lock
from _lpm_merge_effects import qualifies_for_rollout, rollout_update
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_paths import PROOF_RECORD_NAME
from _lpm_proof import CompletionMarker, ProofRecord, proof_object, read_proof_record
from _lpm_proof_binding import proof_binding
from _lpm_proof_contributions import completion_contribution
from _lpm_proof_peers import simultaneous_spread_contribution
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "proof_update",
]

_PROOF_LOCK = "coexistence-proof.lock"


def proof_update(*, context: EffectContext) -> Result[str, ManagerError]:
    """Merge this operation's retained contribution under proof-record serialization."""
    binding = proof_binding(context=context)
    if isinstance(binding, Failure):
        return binding
    held = take_lock(
        path=context.engine.state_dir / "locks" / _PROOF_LOCK,
        owner_uid=context.engine.owner_uid,
        timeout_seconds=context.engine.lock_timeout_seconds,
        monotonic=context.engine.lock_monotonic,
        sleep=context.engine.lock_sleep,
    )
    if isinstance(held, Failure):
        return held
    try:
        return _locked_update(context=context, binding=binding.unwrap())
    finally:
        release_lock(held=held.unwrap())


def _locked_update(
    *, context: EffectContext, binding: Assignment | ClosingRecord
) -> Result[str, ManagerError]:
    path = context.engine.state_dir / PROOF_RECORD_NAME
    stored = read_proof_record(path=path, owner_uid=context.engine.owner_uid)
    if isinstance(stored, Failure):
        return stored
    current = stored.unwrap()
    merged = _merged(context=context, proof=current, binding=binding)
    if isinstance(merged, Failure):
        return merged
    updated = merged.unwrap()
    if updated == current:
        return Success(SATISFIED)
    written = write_local_record(
        path=path, value=proof_object(proof=updated), owner_uid=context.engine.owner_uid
    )
    if isinstance(written, Failure):
        return written
    return Success(PERFORMED)


def _merged(
    *, context: EffectContext, proof: ProofRecord, binding: Assignment | ClosingRecord
) -> Result[ProofRecord, ManagerError]:
    if context.operation.command == "provision":
        return _provision_contribution(
            context=context, proof=proof, assignment=cast("Assignment", binding)
        )
    if context.operation.command == "complete":
        return _completion_contribution(
            context=context, proof=proof, binding=cast("ClosingRecord", binding)
        )
    return Success(proof)


def _provision_contribution(
    *, context: EffectContext, proof: ProofRecord, assignment: Assignment
) -> Result[ProofRecord, ManagerError]:
    request = assignment.request
    if not qualifies_for_rollout(
        provider=str(request["provider"]), purpose=str(request["purpose"])
    ):
        return Success(proof)
    updated = rollout_update(
        proof=proof, target_committed_at=cast("str", assignment.target_committed_at)
    )
    if updated.simultaneous_spread is not None:
        return Success(updated)
    pair = simultaneous_spread_contribution(
        state_dir=context.engine.state_dir,
        owner_uid=context.engine.owner_uid,
        assignment=assignment,
        rollout_started_at=str(updated.rollout_started_at),
    )
    if isinstance(pair, Failure):
        return pair
    contribution = pair.unwrap()
    return Success(
        updated if contribution is None else replace(updated, simultaneous_spread=contribution)
    )


def _completion_contribution(
    *, context: EffectContext, proof: ProofRecord, binding: ClosingRecord
) -> Result[ProofRecord, ManagerError]:
    source = context.operation.normalized_input
    marker = CompletionMarker(
        consumer_run_id=cast("str", source["consumer_run_id"]),
        record_id=cast("str", source["record_id"]),
        completed_at=cast("str", source["completed_at"]),
    )
    if not _qualifying_completion(context=context, proof=proof, binding=binding):
        return Success(proof)
    return Success(completion_contribution(proof=proof, marker=marker))


def _qualifying_completion(
    *, context: EffectContext, proof: ProofRecord, binding: ClosingRecord
) -> bool:
    request = binding.stored["request"]
    normalized = cast("dict[str, object]", request)
    return (
        proof.rollout_started_at is not None
        and normalized["provider"] == "anthropic"
        and normalized["purpose"] == "factory"
        and binding.target_committed_at >= proof.rollout_started_at
        and context.operation.normalized_input["consumer_class"] == "production"
        and context.operation.normalized_input["provider_authenticated"] is True
        and context.operation.normalized_input["alternate_credential_used"] is False
    )
