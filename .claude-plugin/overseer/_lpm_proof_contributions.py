"""Pure canonical completion-marker contributions to the coexistence proof.

The runtime executor owns serialization and authoritative binding reads.  This module owns the
one contribution rule needed beside them: marker identity is a set key and stored order never
depends on concurrent arrival order.
"""

from __future__ import annotations

from dataclasses import replace

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_proof import CompletionMarker, ProofRecord

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "completion_contribution",
]


def completion_contribution(*, proof: ProofRecord, marker: CompletionMarker) -> ProofRecord:
    """Apply one previously-unseen qualifying completion exactly once."""
    by_identity = {
        (held.consumer_run_id, held.record_id): held for held in proof.completion_markers
    }
    by_identity[(marker.consumer_run_id, marker.record_id)] = marker
    markers = tuple(
        sorted(
            by_identity.values(),
            key=lambda held: (held.completed_at, held.consumer_run_id, held.record_id),
        )
    )
    return replace(
        proof,
        completion_markers=markers,
    )
