"""Reconciling a fenced conditional-set, and quarantining only the record that cannot be.

SPECIFICATION/contracts.md requires that after a deadline, interruption, unavailable transport
or malformed adapter result the manager bypass every cache and AUTHORITATIVELY REREAD the
complete metadata revision chain before deciding the effect. An exact desired next revision
carrying that `effect_id` proves the logical effect committed and advances it WITHOUT another
adapter call. Only when the current invocation created the fence FROM ABSENCE and that first
adapter call returned an ordinary definitive result may a different current logical record
prove the condition failed. After an unknown result the expected predecessor or expected
absence proves only that no desired revision was visible by that reread, so the fence is
RETAINED and the call returns `store-unavailable`.

THE ASYMMETRY IS THE POINT, AND IT ONLY RUNS ONE WAY. Evidence that the revision landed is
positive and conclusive; evidence that it did not is merely an absence, and an absence cannot
rule out a create still in flight. So every branch that cannot see the desired revision keeps
the fence, and only the two conclusive branches remove it.

MANDATORY GLOBAL RECOVERY ATTEMPTS FENCES IN LEXICAL `record_id` ORDER, and a record it cannot
reconcile is QUARANTINED FOR THAT INVOCATION ONLY — its fence and owning safety state retained
— while recovery continues for every other record. That bound is what stops one unreconcilable
fence from globally wedging unrelated work: a command whose result does not depend on the
quarantined record proceeds normally, while no command may read, select or mutate that record
as authoritative.

PROVISION'S REFUSAL IS DELIBERATELY NOT `retryable-exhaustion` WHEN QUARANTINE EMPTIED THE
POOL. Exhaustion invites a retry and says the pool answered "none available"; a quarantined
candidate means the manager could not determine the record's state at all. Reporting the
second as the first would have a consumer retry forever against a record nobody can read.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_fence import MetadataFence
from _lpm_operation import OperationRecord
from _lpm_operation_identity import effect_id
from _lpm_operation_plan import writer_role_for
from _lpm_results import ManagerError, internal_bug, retryable_exhaustion, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ADAPTER_OUTCOMES",
    "ADVANCE",
    "CONDITION_FAILED",
    "DESIRED_REVISION",
    "FENCE_DISPOSITIONS",
    "REREAD_OUTCOMES",
    "UNAVAILABLE",
    "UNCOMMITTED",
    "FenceDecision",
    "GlobalRecovery",
    "fence_owner_defect",
    "quarantine_refusal",
    "reconcile_conditional_set",
    "recover_pending_fences",
    "selectable_candidates",
    "stored_terminal_outcome",
]

_COMMITTED: Final = "committed"
_ADAPTER_CONDITION_FAILED: Final = "condition-failed"
_ADAPTER_UNCOMMITTED: Final = "uncommitted"
_UNKNOWN: Final = "unknown"
ADAPTER_OUTCOMES: Final = (_COMMITTED, _ADAPTER_CONDITION_FAILED, _ADAPTER_UNCOMMITTED, _UNKNOWN)

DESIRED_REVISION: Final = "desired"
_EXPECTED: Final = "expected"
_ABSENT: Final = "absent"
_DIFFERENT: Final = "different"
_UNREADABLE: Final = "unreadable"
REREAD_OUTCOMES: Final = (DESIRED_REVISION, _EXPECTED, _ABSENT, _DIFFERENT, _UNREADABLE)

ADVANCE: Final = "advance"
CONDITION_FAILED: Final = "condition-failed"
UNCOMMITTED: Final = "uncommitted"
UNAVAILABLE: Final = "store-unavailable"
FENCE_DISPOSITIONS: Final = (ADVANCE, CONDITION_FAILED, UNCOMMITTED, UNAVAILABLE)


@dataclass(frozen=True, kw_only=True)
class FenceDecision:
    """What a fenced conditional-set resolved to, and whether its fence survives.

    The two travel together because they are decided by the same evidence and are wrong in
    different directions: a retained fence with an advanced effect would block the record's
    next revision forever, while a removed fence with an undecided effect would let a late
    duplicate outrank one.
    """

    disposition: str
    retain_fence: bool


@dataclass(frozen=True, kw_only=True)
class GlobalRecovery:
    """One mandatory global recovery pass over the pending fences it found."""

    reconciled: tuple[str, ...]
    quarantined: tuple[str, ...]


def reconcile_conditional_set(
    *, adapter_outcome: str, created_from_absence: bool, reread: str
) -> Result[FenceDecision, ManagerError]:
    """Decide a fenced conditional-set from its adapter result and authoritative reread."""
    if adapter_outcome not in ADAPTER_OUTCOMES:
        return Failure(internal_bug(message=f"{adapter_outcome} is not an adapter outcome"))
    if reread not in REREAD_OUTCOMES:
        return Failure(internal_bug(message=f"{reread} is not an authoritative reread outcome"))
    return Success(
        _decided(
            adapter_outcome=adapter_outcome,
            created_from_absence=created_from_absence,
            reread=reread,
        )
    )


def _decided(*, adapter_outcome: str, created_from_absence: bool, reread: str) -> FenceDecision:
    if reread == DESIRED_REVISION:
        return FenceDecision(disposition=ADVANCE, retain_fence=False)
    if adapter_outcome in (_COMMITTED, _UNKNOWN) or reread == _UNREADABLE:
        return FenceDecision(disposition=UNAVAILABLE, retain_fence=True)
    if not created_from_absence:
        return _conservative_decision(adapter_outcome=adapter_outcome)
    if adapter_outcome == _ADAPTER_UNCOMMITTED:
        return FenceDecision(disposition=UNCOMMITTED, retain_fence=False)
    if reread == _DIFFERENT:
        return FenceDecision(disposition=CONDITION_FAILED, retain_fence=False)
    return FenceDecision(disposition=UNAVAILABLE, retain_fence=True)


def recover_pending_fences(
    *, record_ids: Sequence[str], reconcile: Callable[[str], Result[object, ManagerError]]
) -> GlobalRecovery:
    """Attempt every pending fence in lexical `record_id` order, quarantining each failure.

    A failure quarantines ONLY its own record and recovery continues, which is what keeps one
    unreconcilable fence from wedging unrelated records. Attempting and quarantining completes
    the global traversal for that record WITHOUT completing or removing its pending effect.
    """
    reconciled: list[str] = []
    quarantined: list[str] = []
    for record_id in sorted(record_ids):
        outcome = reconcile(record_id)
        if isinstance(outcome, Failure):
            quarantined.append(record_id)
        else:
            reconciled.append(record_id)
    return GlobalRecovery(reconciled=tuple(reconciled), quarantined=tuple(quarantined))


def quarantine_refusal(*, record_id: str, quarantined: Collection[str]) -> ManagerError | None:
    """The refusal a command owes when its resolved record identity is quarantined."""
    if record_id in quarantined:
        return store_unavailable(
            message="this record is quarantined by an unreconciled metadata-effect fence"
        )
    return None


def selectable_candidates(
    *, matching: Sequence[str], quarantined: Collection[str]
) -> Result[tuple[str, ...], ManagerError]:
    """The non-quarantined subset of `matching`, or the refusal an empty subset earns.

    An empty subset means two different things and they get two different refusals: a pool
    emptied by QUARANTINE is `store-unavailable`, because nobody can say what those records
    hold, while a pool that was empty anyway is `retryable-exhaustion`, which asks to be
    retried.
    """
    eligible = tuple(record_id for record_id in matching if record_id not in quarantined)
    if eligible:
        return Success(eligible)
    if any(record_id in quarantined for record_id in matching):
        return Failure(
            store_unavailable(
                message="every otherwise matching record is quarantined by a metadata fence"
            )
        )
    return Failure(
        retryable_exhaustion(message="no record matches the requested provider, kind and purpose")
    )


def fence_owner_defect(
    *, fence: MetadataFence, operation: OperationRecord, index: int
) -> str | None:
    """A reason `fence` does not belong to `operation`'s effect at `index`.

    The contract requires fence relation validation to DERIVE the effect identifier, actor and
    writer role from the fence and its owning operation rather than to trust the three values
    stored beside each other — which is also what lets a recovery replay keep the ORIGINAL
    semantic audit actor when another process resumes the operation.
    """
    if fence.owner_operation_id != operation.operation_id:
        return "a fence owner_operation_id must name its owning operation"
    derived = effect_id(operation=operation, index=index)
    if isinstance(derived, Failure):
        return derived.failure().message
    if derived.unwrap() != fence.effect_id:
        return "a fence effect_id must be the owning position's derived identifier"
    role = writer_role_for(
        command=operation.command,
        phase=operation.phase,
        effect=operation.ordered_effects[index],
        outcome=stored_terminal_outcome(operation=operation),
    )
    if isinstance(role, Failure):
        return role.failure().message
    if role.unwrap() != fence.writer_role:
        return "a fence writer_role must equal the owning phase's semantic audit actor"
    return None


def stored_terminal_outcome(*, operation: OperationRecord) -> str | None:
    """`operation`'s stored terminal outcome, or None when it carries no terminal result.

    PUBLIC because the actor table needs it too: `writer_role_for` separates a terminal
    SUCCESS publish from a terminal FAILURE transition on the same effect name, so every
    caller that asks the table for an audited effect's semantic actor has to read the same
    member the same way. A second reader of a nullable member inside a nullable object is
    exactly where two call sites come to disagree about which actor owns a fence.
    """
    stored = operation.terminal_result
    if stored is None:
        return None
    outcome = stored.get("outcome")
    return outcome if isinstance(outcome, str) else None


def _conservative_decision(*, adapter_outcome: str) -> FenceDecision:
    if adapter_outcome == _ADAPTER_UNCOMMITTED:
        return FenceDecision(disposition=UNCOMMITTED, retain_fence=True)
    return FenceDecision(disposition=UNAVAILABLE, retain_fence=True)
