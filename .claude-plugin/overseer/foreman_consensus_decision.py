"""Consensus-panel decision matrix and reviewer validation helpers.

Agreement is decided by this evaluator, not by the reviewer prompt.  Most typed
actions compare by their typed action payload; picker-answer actions project to
the reviewer schema that carries the decision: the action id plus the selected
answer.
"""

from __future__ import annotations

import jsonio
from foreman_consensus_actions import model_for, typed_action
from foreman_consensus_matrix import ReviewerVotes
from foreman_consensus_outcomes import dissent_result, escalation
from foreman_consensus_prompt import str_field
from foreman_consensus_types import DecisionRule
from foreman_valve_policy import MAJORITY, UNANIMOUS

__all__: list[str] = [
    "escalation",
    "reviewer_analysis",
    "reviewers_from",
]


def reviewers_from(*, responses: dict[str, object]) -> list[dict[str, object]]:
    raw = jsonio.as_list(value=responses.get("reviewers")) or []
    reviewers: list[dict[str, object]] = []
    for item in raw:
        reviewer = jsonio.as_object(value=item)
        if reviewer is not None:
            reviewers.append(reviewer)
    return reviewers


def hard_risk_dissent(*, reviewer: dict[str, object]) -> bool:
    return reviewer.get("verdict") == "needs-human" and reviewer.get("hard_risk") is True


def hard_risk_kind(*, reviewer: dict[str, object]) -> str | None:
    value = reviewer.get("risk_kind")
    return value if value in {"security", "other"} else None


def insufficient_tooling_failure(*, reviewer: dict[str, object]) -> bool:
    action = jsonio.as_object(value=reviewer.get("action")) or {}
    params = jsonio.as_object(value=action.get("params")) or {}
    return reviewer.get("verdict") == "insufficient-information" and params.get("reason") in {
        "reviewer_command_missing",
        "reviewer_command_failed",
        "reviewer_response_malformed",
        "reviewer_timeout",
    }


def insufficient_validation_reason(
    *, reviewer: dict[str, object], decision_rule: DecisionRule
) -> str | None:
    if reviewer.get("verdict") != "insufficient-information":
        return None
    if decision_rule == UNANIMOUS or insufficient_tooling_failure(reviewer=reviewer):
        return "insufficient_information"
    return None


def hard_risk_validation_reason(
    *, reviewer: dict[str, object], decision_rule: DecisionRule
) -> str | None:
    if not hard_risk_dissent(reviewer=reviewer):
        return None
    kind = hard_risk_kind(reviewer=reviewer)
    if kind is None:
        return "malformed_response"
    if decision_rule == MAJORITY and kind == "security":
        return "security_dissent"
    return "hard_risk_dissent" if decision_rule == UNANIMOUS else None


def typed_action_validation_reason(
    *, reviewer: dict[str, object], decision_rule: DecisionRule, identity: dict[str, str]
) -> str | None:
    verdict = reviewer.get("verdict")
    action = typed_action(action=reviewer.get("action"))
    if action is None:
        return "free_form_action"
    if verdict == "needs-human" and decision_rule == UNANIMOUS:
        return "non_anthropic_needs_human_dissent" if identity["vendor"] != "anthropic" else None
    valid_verdicts = {"unblock", "needs-human"}
    if decision_rule == MAJORITY:
        valid_verdicts.add("insufficient-information")
    return None if verdict in valid_verdicts else "unknown_verdict"


def reviewer_validation_reason(
    *, reviewer: dict[str, object], decision_rule: DecisionRule
) -> str | None:
    reviewer_id = str_field(payload=reviewer, key="reviewer_id")
    identity = model_for(reviewer_id=reviewer_id)
    if identity is None:
        return "unpinned_model_identity"
    insufficient = insufficient_validation_reason(reviewer=reviewer, decision_rule=decision_rule)
    if insufficient is not None:
        return insufficient
    hard_risk = hard_risk_validation_reason(reviewer=reviewer, decision_rule=decision_rule)
    if hard_risk is not None:
        return hard_risk
    return typed_action_validation_reason(
        reviewer=reviewer, decision_rule=decision_rule, identity=identity
    )


def reviewer_analysis(
    *, request: dict[str, object], reviewers: list[dict[str, object]], decision_rule: DecisionRule
) -> tuple[
    ReviewerVotes,
    dict[str, object] | None,
]:
    needs_human: list[dict[str, object]] = []
    unblockers: list[dict[str, object]] = []
    actions: list[dict[str, object]] = []
    result: dict[str, object] | None = None
    for reviewer in reviewers:
        reason = reviewer_validation_reason(reviewer=reviewer, decision_rule=decision_rule)
        if reason == "non_anthropic_needs_human_dissent":
            result = dissent_result(
                request=request,
                reviewers=reviewers,
                dissent=reviewer,
                decision_rule=decision_rule,
            )
            break
        if reason is not None:
            result = escalation(
                reason=reason,
                request=request,
                reviewers=reviewers,
                decision_rule=decision_rule,
            )
            break
        action = typed_action(action=reviewer.get("action"))
        if action is not None and reviewer.get("verdict") != "insufficient-information":
            actions.append(action)
        if reviewer.get("verdict") == "needs-human":
            needs_human.append(reviewer)
        if reviewer.get("verdict") == "unblock":
            unblockers.append(reviewer)
    return ReviewerVotes(needs_human=needs_human, unblockers=unblockers, actions=actions), result
