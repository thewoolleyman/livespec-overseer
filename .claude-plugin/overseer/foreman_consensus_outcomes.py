"""Panel outcome payloads and the minority-report override policy.

Every consensus outcome is a payload of the same shape, so the builders live
together rather than beside the matrix that chooses between them.  The minority
override joins them because it is the one path that BUILDS an outcome while also
deciding it: it consults the held minority-report round and the reversibility of
the proposed action, and returns either an escalation or an override payload.

`foreman_consensus_decision` keeps the decision matrix and reviewer validation
and imports these; the dependency runs one way only.
"""

from __future__ import annotations

import jsonio
from foreman_consensus_actions import (
    action_is_reversible,
    action_is_rollback_bounded,
    review_record,
    typed_action,
)
from foreman_consensus_present import presentation
from foreman_consensus_prompt import cache_key, str_field
from foreman_consensus_types import MODEL_IDENTITIES, PANEL_SCHEMA_VERSION, DecisionRule

__all__: list[str] = [
    "dissent_result",
    "escalation",
    "held_reviewer_ids",
    "majority",
    "minority_override",
    "unanimous",
]


def escalation(
    *,
    reason: str,
    request: dict[str, object],
    reviewers: list[dict[str, object]],
    decision_rule: DecisionRule,
) -> dict[str, object]:
    action: dict[str, object] = {"action_id": "human_valve", "params": {}}
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "escalate",
        "reason": reason,
        "decision_rule": decision_rule,
        "action": action,
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "presentation": presentation(request=request, reviewers=reviewers, action=action),
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request, decision_rule=decision_rule),
        "mutated": False,
    }


def unanimous(
    *,
    action: dict[str, object],
    request: dict[str, object],
    reviewers: list[dict[str, object]],
    decision_rule: DecisionRule,
) -> dict[str, object]:
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "unanimous",
        "reason": "three_typed_actions_equal",
        "decision_rule": decision_rule,
        "action": action,
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request, decision_rule=decision_rule),
        "mutated": False,
    }


def majority(
    *,
    action: dict[str, object],
    request: dict[str, object],
    reviewers: list[dict[str, object]],
    decision_rule: DecisionRule,
    dissent: dict[str, object] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "majority",
        "reason": "two_unblock_typed_actions_equal",
        "decision_rule": decision_rule,
        "action": action,
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request, decision_rule=decision_rule),
        "mutated": False,
    }
    if dissent is not None:
        result["dissent"] = review_record(reviewer=dissent)
    return result


def dissent_result(
    *,
    request: dict[str, object],
    reviewers: list[dict[str, object]],
    dissent: dict[str, object],
    decision_rule: DecisionRule,
) -> dict[str, object]:
    result = escalation(
        reason="non_anthropic_needs_human_dissent",
        request=request,
        reviewers=reviewers,
        decision_rule=decision_rule,
    )
    result["dissent"] = review_record(reviewer=dissent)
    return result


def held_reviewer_ids(*, responses: dict[str, object], required: set[str]) -> list[str] | None:
    round_payload = jsonio.as_object(value=responses.get("minority_report_round"))
    if round_payload is None:
        return None
    raw_holders = jsonio.as_list(value=round_payload.get("holders")) or []
    held: list[str] = []
    for raw in raw_holders:
        holder = jsonio.as_object(value=raw)
        if holder is None or holder.get("holds") is not True:
            continue
        reviewer_id = str_field(payload=holder, key="reviewer_id")
        if reviewer_id in required:
            held.append(reviewer_id)
    return held if set(held) == required else []


def minority_override(
    *,
    request: dict[str, object],
    reviewers: list[dict[str, object]],
    responses: dict[str, object],
    dissent: dict[str, object],
    unblockers: list[dict[str, object]],
    decision_rule: DecisionRule,
) -> dict[str, object]:
    round_held = held_reviewer_ids(
        responses=responses,
        required={str_field(payload=reviewer, key="reviewer_id") for reviewer in unblockers},
    )
    if round_held is None:
        return escalation(
            reason="needs_human",
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    if not action_is_reversible(action=unblockers[0].get("action")):
        return escalation(
            reason="minority_action_not_reversible",
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    if not action_is_rollback_bounded(action=unblockers[0].get("action")):
        return escalation(
            reason="minority_action_not_rollback_bounded",
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    if not round_held:
        return escalation(
            reason="minority_report_not_held",
            request=request,
            reviewers=reviewers,
            decision_rule=decision_rule,
        )
    action = typed_action(action=unblockers[0].get("action")) or {}
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "minority_override",
        "reason": "minority_report_both_holders_confirmed",
        "decision_rule": decision_rule,
        "action": action,
        "dissent": review_record(reviewer=dissent),
        "minority_report_round": {"held_by": round_held},
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request, decision_rule=decision_rule),
        "mutated": False,
    }
