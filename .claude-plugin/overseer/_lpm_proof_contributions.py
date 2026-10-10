"""Pure canonical completion-marker contributions to the coexistence proof.

The runtime executor owns serialization and authoritative binding reads.  This module owns the
one contribution rule needed beside them: marker identity is a set key and stored order never
depends on concurrent arrival order.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_proof import CompletionMarker, ProofRecord

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "authentication_contribution",
    "completion_contribution",
]


def completion_contribution(
    *, proof: ProofRecord, marker: CompletionMarker, legacy_pool_absent: bool
) -> ProofRecord:
    """Apply one previously-unseen qualifying completion exactly once."""
    identity = (marker.consumer_run_id, marker.record_id)
    if identity in [(held.consumer_run_id, held.record_id) for held in proof.completion_markers]:
        return proof
    by_identity = {
        (held.consumer_run_id, held.record_id): held for held in proof.completion_markers
    }
    by_identity[identity] = marker
    markers = tuple(
        sorted(
            by_identity.values(),
            key=lambda held: (held.completed_at, held.consumer_run_id, held.record_id),
        )
    )
    evidence = {
        "consumer_run_id": marker.consumer_run_id,
        "completed_at": marker.completed_at,
    }
    dates, soak_started_at = _dated_soak(proof=proof, marker=marker)
    return replace(
        proof,
        completion_markers=markers,
        successful_consumer_dates=dates,
        soak_started_at=soak_started_at,
        production_success=proof.production_success or evidence,
        legacy_pool_absence_success=(
            proof.legacy_pool_absence_success
            if proof.legacy_pool_absence_success is not None or not legacy_pool_absent
            else evidence
        ),
    )


def _dated_soak(
    *, proof: ProofRecord, marker: CompletionMarker
) -> tuple[tuple[str, ...], str | None]:
    if proof.last_auth_failure_at is not None and marker.completed_at <= proof.last_auth_failure_at:
        return proof.successful_consumer_dates, proof.soak_started_at
    observed_date = marker.completed_at[:10]
    if not proof.successful_consumer_dates:
        return (observed_date,), marker.completed_at
    latest = proof.successful_consumer_dates[-1]
    if observed_date <= latest:
        return proof.successful_consumer_dates, proof.soak_started_at
    if date.fromisoformat(observed_date) == date.fromisoformat(latest) + timedelta(days=1):
        return (*proof.successful_consumer_dates, observed_date), proof.soak_started_at
    return (observed_date,), marker.completed_at


def authentication_contribution(*, proof: ProofRecord, occurred_at: str) -> ProofRecord:
    """Advance failure time and clear only a soak that had begun by this event."""
    preserve_soak = proof.soak_started_at is not None and occurred_at < proof.soak_started_at
    return replace(
        proof,
        successful_consumer_dates=(proof.successful_consumer_dates if preserve_soak else ()),
        soak_started_at=proof.soak_started_at if preserve_soak else None,
        last_auth_failure_at=max(proof.last_auth_failure_at or occurred_at, occurred_at),
    )
