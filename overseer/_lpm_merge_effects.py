"""The two read-modify-write merges, written so a replay cannot destroy a concurrent peer.

SPECIFICATION/contracts.md makes `selection-update` and `proof-update` the two provision
`postcommit` effects that mutate a SHARED record, and requires every read-modify-write of
`selection-state.json` and `coexistence-proof.json` to hold its named exclusive lock through atomic
replacement, "preventing lost updates across runs". For the proof it further fixes the two
run-scoped rules: a committed `anthropic` `factory` assignment sets or RETAINS `rollout_started_at`
— set when the field is null or the new time is EARLIER, retained otherwise — and a qualifying
completion whose marker is already present makes `proof-update` a COMPLETED NO-OP that must not
reapply any one-time rule.

A MERGE IS NOT A WRITE, AND THAT IS THE WHOLE POINT OF THIS MODULE. These two records are shared
across runs, so a replay re-entering at an old checkpoint must not carry a stale SNAPSHOT forward.
Each function here therefore takes the record as currently read and returns a record differing only
in the ONE row or field this contribution owns: another provider's incumbent, another run's
completion marker and a later peer's fields survive by construction rather than by the caller
remembering to preserve them. Writing a remembered whole-record snapshot is the lost-update bug the
lock exists to prevent, and a lock cannot prevent it when the stale value is inside the writer.

THE TWO POSTCONDITIONS ARE ASKABLE SEPARATELY FROM THE MERGE, which is what lets a positional
replay answer "is this position already satisfied?" without performing it. `is_*_satisfied` is the
same comparison the merge would make, exposed so the executor can advance its checkpoint on an
already-authoritative record instead of rewriting it.

`rollout_started_at` MOVES ONLY EARLIER. The contract says to set it when null or when the new time
is earlier and otherwise RETAIN it, so a late replay of an early commit corrects the field while a
replay of a LATER commit leaves it alone — the field converges on the earliest committed rollout
regardless of the order the contributions arrive in, which is what makes it stable under retry.
"""

from __future__ import annotations

from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_proof import CompletionMarker, ProofRecord
from _lpm_selection_state import Incumbent, LastAssignment, SelectionState

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ROLLOUT_PROVIDER",
    "ROLLOUT_PURPOSE",
    "completion_marker_update",
    "is_completion_marker_recorded",
    "is_incumbent_recorded",
    "is_rollout_satisfied",
    "last_assignment_update",
    "qualifies_for_rollout",
    "rollout_update",
    "selection_incumbent_update",
]

ROLLOUT_PROVIDER: Final = "anthropic"
ROLLOUT_PURPOSE: Final = "factory"


def selection_incumbent_update(
    *,
    state: SelectionState,
    provider: str,
    kind: str,
    purpose: str,
    record_id: str,
    target_committed_at: str,
) -> SelectionState:
    """The selection state with THIS row's incumbent set, every other row untouched.

    The row identity is the provider/kind/purpose triple, so a concurrent contribution for a
    different triple — or a `spread` run's `last_assignments` entry — is carried forward verbatim.
    """
    retained = tuple(
        incumbent
        for incumbent in state.incumbents
        if (incumbent.provider, incumbent.kind, incumbent.purpose) != (provider, kind, purpose)
    )
    return SelectionState(
        incumbents=(
            *retained,
            Incumbent(
                provider=provider,
                kind=kind,
                purpose=purpose,
                record_id=record_id,
                target_committed_at=target_committed_at,
            ),
        ),
        last_assignments=state.last_assignments,
    )


def last_assignment_update(
    *, state: SelectionState, record_id: str, assigned_at: str
) -> SelectionState:
    """The selection state with THIS record's last-assignment time set, incumbents untouched."""
    retained = tuple(entry for entry in state.last_assignments if entry.record_id != record_id)
    return SelectionState(
        incumbents=state.incumbents,
        last_assignments=(
            *retained,
            LastAssignment(record_id=record_id, assigned_at=assigned_at),
        ),
    )


def is_incumbent_recorded(
    *,
    state: SelectionState,
    provider: str,
    kind: str,
    purpose: str,
    record_id: str,
    target_committed_at: str,
) -> bool:
    """Whether this row's incumbent is already exactly this contribution's."""
    return (
        Incumbent(
            provider=provider,
            kind=kind,
            purpose=purpose,
            record_id=record_id,
            target_committed_at=target_committed_at,
        )
        in state.incumbents
    )


def qualifies_for_rollout(*, provider: str, purpose: str) -> bool:
    """Whether a committed assignment is one the rollout-start rule applies to at all."""
    return provider == ROLLOUT_PROVIDER and purpose == ROLLOUT_PURPOSE


def rollout_update(*, proof: ProofRecord, target_committed_at: str) -> ProofRecord:
    """The proof record with `rollout_started_at` set or RETAINED, every other field untouched.

    Only ever moved EARLIER. A replay of an early commit corrects the field; a replay of a later
    commit leaves it alone. The field therefore converges on the earliest committed rollout whatever
    order the contributions arrive in.
    """
    if is_rollout_satisfied(proof=proof, target_committed_at=target_committed_at):
        return proof
    return ProofRecord(
        rollout_started_at=target_committed_at,
        successful_consumer_dates=proof.successful_consumer_dates,
        completion_markers=proof.completion_markers,
        soak_started_at=proof.soak_started_at,
        simultaneous_spread=proof.simultaneous_spread,
        production_success=proof.production_success,
        legacy_pool_absence_success=proof.legacy_pool_absence_success,
        last_auth_failure_at=proof.last_auth_failure_at,
    )


def is_rollout_satisfied(*, proof: ProofRecord, target_committed_at: str) -> bool:
    """Whether the stored rollout start already is, or already precedes, this commit."""
    stored = proof.rollout_started_at
    return stored is not None and stored <= target_committed_at


def completion_marker_update(*, proof: ProofRecord, marker: CompletionMarker) -> ProofRecord:
    """The proof record with `marker` inserted in canonical order, or exactly as it was.

    The already-present case returns the SAME record, so a repeated contribution cannot reapply a
    one-time rule — which is the contract's stated reason for making it a completed no-op rather
    than an idempotent re-write.
    """
    if is_completion_marker_recorded(proof=proof, marker=marker):
        return proof
    return ProofRecord(
        rollout_started_at=proof.rollout_started_at,
        successful_consumer_dates=proof.successful_consumer_dates,
        completion_markers=_ordered_markers(markers=(*proof.completion_markers, marker)),
        soak_started_at=proof.soak_started_at,
        simultaneous_spread=proof.simultaneous_spread,
        production_success=proof.production_success,
        legacy_pool_absence_success=proof.legacy_pool_absence_success,
        last_auth_failure_at=proof.last_auth_failure_at,
    )


def is_completion_marker_recorded(*, proof: ProofRecord, marker: CompletionMarker) -> bool:
    """Whether this contribution's identity — run plus record — is already recorded."""
    identity = (marker.consumer_run_id, marker.record_id)
    return identity in [
        (recorded.consumer_run_id, recorded.record_id) for recorded in proof.completion_markers
    ]


def _ordered_markers(*, markers: tuple[CompletionMarker, ...]) -> tuple[CompletionMarker, ...]:
    return tuple(
        sorted(
            markers,
            key=lambda marker: (marker.completed_at, marker.consumer_run_id, marker.record_id),
        )
    )
