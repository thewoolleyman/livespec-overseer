"""Typed verdict evaluation for the report-only consensus panel."""

from __future__ import annotations

from foreman_consensus_decision import (
    decision_matrix_result,
    escalation,
    reviewer_analysis,
    reviewers_from,
)
from foreman_consensus_types import MODEL_IDENTITIES

__all__: list[str] = [
    "escalation",
    "evaluate_verdicts",
]


def evaluate_verdicts(
    *, request: dict[str, object], responses: dict[str, object]
) -> dict[str, object]:
    reviewers = reviewers_from(responses=responses)
    if len(reviewers) != len(MODEL_IDENTITIES):
        return escalation(reason="panel_size_mismatch", request=request, reviewers=reviewers)
    needs_human, unblockers, actions, result = reviewer_analysis(
        request=request, reviewers=reviewers
    )
    if result is not None:
        return result
    return decision_matrix_result(
        request=request,
        responses=responses,
        reviewers=reviewers,
        needs_human=needs_human,
        unblockers=unblockers,
        actions=actions,
    )
