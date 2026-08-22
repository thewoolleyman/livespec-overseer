"""Classify foreman panel verdicts as tooling outages or substantive non-decisions."""

from __future__ import annotations

from typing import Final

import jsonio

__all__: list[str] = ["result_decision_kind"]

TOOLING_FAILURE_REASONS: Final[frozenset[str]] = frozenset(
    {
        "reviewer_command_missing",
        "reviewer_command_failed",
        "reviewer_response_malformed",
        "reviewer_timeout",
    }
)
TOOLING_VERDICT_REASONS: Final[frozenset[str]] = frozenset(
    {"malformed_response", "unpinned_model_identity"}
)


def reviewer_failure_reason(*, reviewer: dict[str, object]) -> str:
    action = jsonio.as_object(value=reviewer.get("action")) or {}
    params = jsonio.as_object(value=action.get("params")) or {}
    reason = params.get("reason")
    return reason if isinstance(reason, str) else ""


def result_decision_kind(*, reviewers: list[dict[str, object]], verdict_reason: str = "") -> str:
    if verdict_reason in TOOLING_VERDICT_REASONS:
        return "tooling_outage"
    if any(
        reviewer_failure_reason(reviewer=reviewer) in TOOLING_FAILURE_REASONS
        for reviewer in reviewers
    ):
        return "tooling_outage"
    return "substantive_non_decision"
