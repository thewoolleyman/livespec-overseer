"""Consensus-panel decision matrix and reviewer validation helpers.

Agreement is decided by this evaluator, not by the reviewer prompt.  Most typed
actions compare by their typed action payload; picker-answer actions project to
the reviewer schema that carries the decision: the action id plus the selected
answer.
"""

from __future__ import annotations

import jsonio
from foreman_consensus_actions import model_for, typed_action
from foreman_consensus_outcomes import (
    dissent_result,
    escalation,
    majority,
    minority_override,
    unanimous,
)
from foreman_consensus_prompt import canonical_json, str_field

_ONE = 1
_TWO = 2

__all__: list[str] = [
    "decision_matrix_result",
    "escalation",
    "reviewer_analysis",
    "reviewers_from",
]


def _consensus_key(*, action: dict[str, object]) -> dict[str, object]:
    if action.get("action_id") != "blocked_session_answer":
        return action
    params = jsonio.as_object(value=action.get("params")) or {}
    return {
        "action_id": action.get("action_id"),
        "params": {"answer": _selected_answer(params=params)},
    }


def _selected_answer(*, params: dict[str, object]) -> str | None:
    answer = params.get("answer")
    if isinstance(answer, str):
        return answer
    legacy = params.get("answer_text")
    return legacy if isinstance(legacy, str) else None


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


def reviewer_validation_reason(*, reviewer: dict[str, object]) -> str | None:
    reviewer_id = str_field(payload=reviewer, key="reviewer_id")
    identity = model_for(reviewer_id=reviewer_id)
    if identity is None:
        return "unpinned_model_identity"
    verdict = reviewer.get("verdict")
    if verdict == "insufficient-information":
        return "insufficient_information"
    if hard_risk_dissent(reviewer=reviewer):
        return "hard_risk_dissent"
    action = typed_action(action=reviewer.get("action"))
    if action is None:
        return "free_form_action"
    if verdict == "needs-human":
        return "non_anthropic_needs_human_dissent" if identity["vendor"] != "anthropic" else None
    return None if verdict == "unblock" else "unknown_verdict"


def reviewer_analysis(
    *, request: dict[str, object], reviewers: list[dict[str, object]]
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object] | None,
]:
    needs_human: list[dict[str, object]] = []
    unblockers: list[dict[str, object]] = []
    actions: list[dict[str, object]] = []
    result: dict[str, object] | None = None
    for reviewer in reviewers:
        reason = reviewer_validation_reason(reviewer=reviewer)
        if reason == "non_anthropic_needs_human_dissent":
            result = dissent_result(request=request, reviewers=reviewers, dissent=reviewer)
            break
        if reason is not None:
            result = escalation(reason=reason, request=request, reviewers=reviewers)
            break
        action = typed_action(action=reviewer.get("action"))
        if action is not None:  # pragma: no branch
            actions.append(action)
        if reviewer.get("verdict") == "needs-human":
            needs_human.append(reviewer)
        if reviewer.get("verdict") == "unblock":
            unblockers.append(reviewer)
    return needs_human, unblockers, actions, result


def majority_action(*, actions: list[dict[str, object]]) -> dict[str, object] | None:
    counts: dict[str, int] = {}
    representatives: dict[str, dict[str, object]] = {}
    for action in actions:
        if action.get("action_id") != "blocked_session_answer":
            return None
        key = canonical_json(value=_consensus_key(action=action))
        counts[key] = counts.get(key, 0) + 1
        representatives[key] = action
    winners = [key for key, count in counts.items() if count == _TWO]
    if len(winners) != _ONE:
        return None
    return representatives[winners[0]]


def decision_matrix_result(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    reviewers: list[dict[str, object]],
    needs_human: list[dict[str, object]],
    unblockers: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> dict[str, object]:
    canonical = {canonical_json(value=_consensus_key(action=action)) for action in actions}
    unblocker_canonical = {
        canonical_json(
            value=_consensus_key(action=typed_action(action=reviewer.get("action")) or {})
        )
        for reviewer in unblockers
    }
    if not needs_human and len(canonical) == _ONE:
        return unanimous(action=actions[0], request=request, reviewers=reviewers)
    if not needs_human:
        action = majority_action(actions=actions)
        if action is not None:
            return majority(action=action, request=request, reviewers=reviewers)
    if len(needs_human) == _ONE and len(unblockers) == _TWO:
        if len(unblocker_canonical) == _ONE and len(canonical) == _TWO:
            return minority_override(
                request=request,
                reviewers=reviewers,
                responses=responses,
                dissent=needs_human[0],
                unblockers=unblockers,
            )
        return escalation(reason="typed_action_disagreement", request=request, reviewers=reviewers)
    if needs_human:
        return escalation(reason="needs_human", request=request, reviewers=reviewers)
    return escalation(reason="typed_action_disagreement", request=request, reviewers=reviewers)
