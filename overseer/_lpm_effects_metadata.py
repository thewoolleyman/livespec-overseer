"""`credential-conditional-set`: one fenced append-only revision, decided by a real reread.

SPECIFICATION/contracts.md requires every conditional set to carry "the complete expected
logical predecessor, which MAY be absent, the complete canonical desired replacement and the
effect's `effect_id`"; to "atomically create this file from absence or find it byte-identical"
under the credential-record lock BEFORE the adapter's physical-create call; to retain the fence
on every unknown outcome; and to remove it "before advancing the effect" once an authoritative
desired revision is visible. Its `writer_role` "MUST equal the semantic audit actor assigned to
that owning operation, phase and effect by the actor table".

THE FENCE IS CLAIMED BEFORE THE CALL AND RESOLVED AFTER THE DECISION, in that order, because an
existing fence cannot distinguish a crash BEFORE the adapter call from a crash AFTER it. The
claim carries that fact forward — `created_from_absence` is false for an inherited fence — and
the reconciliation treats an inherited fence conservatively, which is the only reason a
definitive `condition-failed` from this invocation's own first call may be believed at all.

ONLY THE AUTHORITATIVE DESIRED REVISION ADVANCES THIS POSITION. Every other disposition is a
CLOSED FAILURE with the fence left exactly where the reconciliation put it: retained when the
outcome is unknown, removed only when this invocation's absence-create earned a definitive
result. A disposition that advanced on an acknowledgement rather than on a reread would make a
lost transport look like a committed transition, which is the failure the fence exists for.

NEITHER THE FENCE BUILD NOR THE FENCED APPLY CAN REFUSE FROM HERE, and both are unwrapped with
that stated rather than guarded. `fence_for_effect` refuses an unencodable or relation-invalid
fence, and both records it is handed came out of `credential_record_from_object` and the actor
table a moment earlier; `apply_fenced_set` refuses only an adapter outcome or reread
classification outside its own closed sets, both of which it computes itself. A guard on either
would be a branch no test could reach, and an unreachable guard is indistinguishable from an
untested one.
"""

from __future__ import annotations

from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine_context import EffectContext
from _lpm_fence import fence_for_effect
from _lpm_fence_recovery import ADVANCE, FenceDecision
from _lpm_fence_reread import apply_fenced_set
from _lpm_fence_store import claim_fence, fence_path, resolve_fence
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_report_credential import ReportTransition, audited_actor, report_transition
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "credential_conditional_set",
]


def credential_conditional_set(*, context: EffectContext) -> Result[str, ManagerError]:
    """Append this report's one fenced lifecycle revision, or settle its completed no-op."""
    transition = report_transition(context=context)
    if isinstance(transition, Failure):
        return Failure(transition.failure())
    planned = transition.unwrap()
    if planned is None:
        return Success(SATISFIED)
    actor = audited_actor(context=context)
    if isinstance(actor, Failure):
        return actor
    decided = _fenced(context=context, planned=planned, writer_role=actor.unwrap())
    if isinstance(decided, Failure):
        return Failure(decided.failure())
    disposition = decided.unwrap().disposition
    if disposition != ADVANCE:
        return Failure(
            store_unavailable(message=f"this record's fenced revision resolved to {disposition}")
        )
    return Success(PERFORMED)


def _fenced(
    *, context: EffectContext, planned: ReportTransition, writer_role: str
) -> Result[FenceDecision, ManagerError]:
    # Neither unwrap can refuse here; see the module docstring's last paragraph.
    fence = fence_for_effect(
        effect_id=context.position.effect_id,
        writer_role=writer_role,
        revision=planned.revision,
        expected_record=planned.expected_record,
        desired_record=planned.desired_record,
        owner_operation_id=context.operation.operation_id,
    ).unwrap()
    path = _fence_file(context=context, record_id=planned.record_id)
    claim = claim_fence(path=path, fence=fence, owner_uid=context.engine.owner_uid)
    if isinstance(claim, Failure):
        return Failure(claim.failure())
    decision = apply_fenced_set(
        store=context.engine.store,
        fence=fence,
        created_from_absence=claim.unwrap().created_from_absence,
    ).unwrap()
    if decision.retain_fence:
        return Success(decision)
    resolved = resolve_fence(path=path, owner_uid=context.engine.owner_uid)
    if isinstance(resolved, Failure):
        return Failure(resolved.failure())
    return Success(decision)


def _fence_file(*, context: EffectContext, record_id: str) -> Path:
    # The fence family and its single-value identity come from the contract's own local path
    # table, so this lookup has no refusal to report; an unwrap failure would be a defect in
    # that table rather than an operator-visible condition.
    return fence_path(state_dir=context.engine.state_dir, record_id=record_id).unwrap()
