"""Decision-rule matrix for validated foreman consensus reviewer votes."""

from __future__ import annotations

from dataclasses import dataclass

import jsonio
from foreman_consensus_actions import typed_action
from foreman_consensus_outcomes import escalation, majority, minority_override, unanimous
from foreman_consensus_prompt import canonical_json
from foreman_consensus_types import DecisionRule
from foreman_valve_policy import MAJORITY

_ONE = 1
_TWO = 2

__all__: list[str] = [
    "ReviewerVotes",
    "decision_matrix_result",
]


@dataclass(frozen=True, kw_only=True)
class ReviewerVotes:
    needs_human: list[dict[str, object]]
    unblockers: list[dict[str, object]]
    actions: list[dict[str, object]]


def _selected_answer(*, params: dict[str, object]) -> str | None:
    answer = params.get("answer")
    if isinstance(answer, str):
        return answer
    legacy = params.get("answer_text")
    return legacy if isinstance(legacy, str) else None


def _consensus_key(*, action: dict[str, object]) -> dict[str, object]:
    if action.get("action_id") != "blocked_session_answer":
        return action
    params = jsonio.as_object(value=action.get("params")) or {}
    return {
        "action_id": action.get("action_id"),
        "params": {"answer": _selected_answer(params=params)},
    }


def _majority_action(*, actions: list[dict[str, object]]) -> dict[str, object] | None:
    counts: dict[str, int] = {}
    representatives: dict[str, dict[str, object]] = {}
    for action in actions:
        key = canonical_json(value=_consensus_key(action=action))
        counts[key] = counts.get(key, 0) + 1
        representatives[key] = action
    winners = [key for key, count in counts.items() if count >= _TWO]
    if len(winners) != _ONE:
        return None
    return representatives[winners[0]]


def _majority_matrix_result(
    *,
    request: dict[str, object],
    reviewers: list[dict[str, object]],
    votes: ReviewerVotes,
    decision_rule: DecisionRule,
) -> dict[str, object]:
    action = _majority_action(actions=votes.actions)
    if action is not None:
        if action.get("action_id") == "human_valve":
            return escalation(
                reason="needs_human",
                request=request,
                reviewers=reviewers,
                decision_rule=decision_rule,
            )
        dissent = votes.needs_human[0] if len(votes.needs_human) == _ONE else None
        return majority(
            action=action,
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
            dissent=dissent,
        )
    reason = (
        "needs_human"
        if len(votes.needs_human) > len(votes.actions)
        else "typed_action_disagreement"
    )
    return escalation(
        reason=reason,
        request=request,
        reviewers=reviewers,
        decision_rule=decision_rule,
    )


def _unanimous_matrix_result(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    reviewers: list[dict[str, object]],
    votes: ReviewerVotes,
    decision_rule: DecisionRule,
) -> dict[str, object]:
    canonical = {canonical_json(value=_consensus_key(action=action)) for action in votes.actions}
    unblocker_canonical = {
        canonical_json(
            value=_consensus_key(action=typed_action(action=reviewer.get("action")) or {})
        )
        for reviewer in votes.unblockers
    }
    if not votes.needs_human and len(canonical) == _ONE:
        return unanimous(
            action=votes.actions[0],
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    if len(votes.needs_human) == _ONE and len(votes.unblockers) == _TWO:
        if len(unblocker_canonical) == _ONE and len(canonical) == _TWO:
            return minority_override(
                request=request,
                reviewers=reviewers,
                responses=responses,
                dissent=votes.needs_human[0],
                unblockers=votes.unblockers,
                decision_rule=decision_rule,
            )
        return escalation(
            reason="typed_action_disagreement",
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    if votes.needs_human:
        return escalation(
            reason="needs_human",
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    return escalation(
        reason="typed_action_disagreement",
        request=request,
        reviewers=reviewers,
        decision_rule=decision_rule,
    )


def decision_matrix_result(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    reviewers: list[dict[str, object]],
    votes: ReviewerVotes,
    decision_rule: DecisionRule,
) -> dict[str, object]:
    if decision_rule == MAJORITY:
        return _majority_matrix_result(
            request=request,
            reviewers=reviewers,
            votes=votes,
            decision_rule=decision_rule,
        )
    return _unanimous_matrix_result(
        request=request,
        responses=responses,
        reviewers=reviewers,
        votes=votes,
        decision_rule=decision_rule,
    )
