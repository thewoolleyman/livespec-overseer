"""`selection-update` and `proof-update`: the two idempotent monotone-merge executors.

SPECIFICATION/contracts.md treats these two apart from every other effect, and says why:
"`selection-update` MUST be an idempotent monotone-merge effect. `proof-update` MUST make each
operation idempotent through its retained contribution postcondition... Both effects are
exempt from generic exact-predecessor refusal. On every first execution or replay, the effect
MUST take its named global lock and reread the current authoritative record. An already
contained contribution MUST advance `completed_step` without recomputing or reapplying that
event's derived changes; otherwise the effect MUST compute its contract-defined update against
the current record and atomically persist it while retaining every concurrent later
contribution."

THAT EXEMPTION IS THE POINT, AND IT IS WHY THESE TWO CANNOT USE AN EXACT-PREDECESSOR TEST.
Every other effect owns its record: a value that is neither the desired one nor the exact
expected predecessor is a refusal. These two records are SHARED across concurrent runs, so by
the time a replay arrives the stored record legitimately carries other runs' contributions —
and refusing on "this is not what I expected" would turn a healthy concurrent write into a
wedged operation.

SO THE POSTCONDITION IS "IS MY CONTRIBUTION CONTAINED?", NOT "IS THE RECORD WHAT I WROTE?".
Both executors reread, merge their own contribution into whatever is there now, and compare the
MERGED object against the stored one. Equality means the contribution is already contained — a
replay settles — and inequality means it is not, so the merge is persisted with every peer
contribution carried through untouched. One comparison expresses both halves, and neither can
drift from the other.

EVERY CONTRIBUTED INSTANT IS A STORED ONE. `target_committed_at` comes from the committed
assignment, which took it from the persisted adapter commit; nothing here reads a clock. A
merge that re-sampled would make its own comparison unstable, so a replay would rewrite the
shared record forever and each rewrite would race the peers it was supposed to preserve.
"""

from __future__ import annotations

from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import COMMITTED_STATUS, Assignment, assignment_from_object
from _lpm_engine_context import EffectContext, input_text
from _lpm_engine_records import stored_record
from _lpm_localstate import write_local_record
from _lpm_merge_effects import last_assignment_update
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_paths import SELECTION_STATE_NAME
from _lpm_proof_effect import proof_update
from _lpm_results import ManagerError, store_unavailable
from _lpm_selection_state import (
    Incumbent,
    SelectionState,
    read_selection_state,
    selection_state_object,
)
from _lpm_strategy import CONSUME_FIRST_STRATEGY

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "committed_assignment",
    "proof_update",
    "selection_update",
]


def committed_assignment(*, context: EffectContext) -> Result[Assignment, ManagerError]:
    """The COMMITTED assignment this operation's merge contributes on behalf of.

    A merge is defined against a committed target, so a prepared or absent assignment is a
    refusal rather than a quiet no-op: contributing nothing would leave the shared record
    silently missing an incumbent or a rollout start that the contract requires.
    """
    run_id = input_text(operation=context.operation, member="consumer_run_id")
    if isinstance(run_id, Failure):
        return run_id
    found = stored_record(context=context, family="assignment", identity=(run_id.unwrap(),))
    if isinstance(found, Failure):
        return Failure(found.failure())
    stored = found.unwrap()
    if stored is None:
        return Failure(store_unavailable(message="no assignment stands for this merge effect"))
    parsed = assignment_from_object(parsed=stored)
    if isinstance(parsed, Failure):
        return parsed
    assignment = parsed.unwrap()
    if assignment.status != COMMITTED_STATUS or assignment.target_committed_at is None:
        return Failure(
            store_unavailable(message="a merge effect contributes only a committed assignment")
        )
    return Success(assignment)


def selection_update(*, context: EffectContext) -> Result[str, ManagerError]:
    """Merge this commit's incumbent and assignment time into the shared selection state.

    The two halves follow different contract rules and both are monotone. Every target commit
    sets its record's assignment time to "the later of stored `assigned_at` and that
    assignment's `target_committed_at`", so a delayed post-commit recovery cannot pull the
    time backwards. The incumbent moves only for a `consume-first` commit, and only when the
    tuple of its `target_committed_at` and `record_id` is lexically later than the stored
    tuple — "a `spread` commit MUST leave every incumbent unchanged" — which is what makes a
    late recovery unable to regress newer selection state.
    """
    assignment = committed_assignment(context=context)
    if isinstance(assignment, Failure):
        return assignment
    bound = assignment.unwrap()
    path = context.engine.state_dir / SELECTION_STATE_NAME
    stored = read_selection_state(path=path, owner_uid=context.engine.owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    current = stored.unwrap()
    merged = _merged_selection(state=current, assignment=bound)
    return _persisted(
        context=context,
        path=path,
        before=selection_state_object(state=current),
        after=selection_state_object(state=merged),
    )


def _merged_selection(*, state: SelectionState, assignment: Assignment) -> SelectionState:
    committed_at = str(assignment.target_committed_at)
    merged = last_assignment_update(
        state=state,
        record_id=assignment.record_id,
        assigned_at=_later_assignment_time(
            state=state, record_id=assignment.record_id, committed_at=committed_at
        ),
    )
    if assignment.request.get("strategy") != CONSUME_FIRST_STRATEGY:
        return merged
    return _incumbent_merged(state=merged, assignment=assignment, committed_at=committed_at)


def _later_assignment_time(*, state: SelectionState, record_id: str, committed_at: str) -> str:
    stored = [entry.assigned_at for entry in state.last_assignments if entry.record_id == record_id]
    return max([committed_at, *stored])


def _incumbent_merged(
    *, state: SelectionState, assignment: Assignment, committed_at: str
) -> SelectionState:
    provider = str(assignment.request["provider"])
    kind = str(assignment.request["kind"])
    purpose = str(assignment.request["purpose"])
    candidate = (committed_at, assignment.record_id)
    retained: list[Incumbent] = []
    for incumbent in state.incumbents:
        if (incumbent.provider, incumbent.kind, incumbent.purpose) != (provider, kind, purpose):
            retained.append(incumbent)
        elif (incumbent.target_committed_at, incumbent.record_id) >= candidate:
            return state
    return SelectionState(
        incumbents=(
            *retained,
            Incumbent(
                provider=provider,
                kind=kind,
                purpose=purpose,
                record_id=assignment.record_id,
                target_committed_at=committed_at,
            ),
        ),
        last_assignments=state.last_assignments,
    )


def _persisted(
    *,
    context: EffectContext,
    path: Path,
    before: dict[str, object],
    after: dict[str, object],
) -> Result[str, ManagerError]:
    """Settle when the merged object already equals the stored one; otherwise persist it."""
    if before == after:
        return Success(SATISFIED)
    written = write_local_record(path=path, value=after, owner_uid=context.engine.owner_uid)
    if isinstance(written, Failure):
        return Failure(written.failure())
    return Success(PERFORMED)
