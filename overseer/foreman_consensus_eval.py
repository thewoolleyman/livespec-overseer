"""Typed verdict evaluation for the report-only consensus panel."""

from __future__ import annotations

import jsonio
from foreman_consensus_prompt import cache_key, canonical_json, str_field
from foreman_consensus_types import ACTION_ID_SET, MODEL_IDENTITIES, PANEL_SCHEMA_VERSION

__all__: list[str] = [
    "escalation",
    "evaluate_verdicts",
]


def reviewers_from(*, responses: dict[str, object]) -> list[dict[str, object]]:
    raw = jsonio.as_list(value=responses.get("reviewers")) or []
    reviewers: list[dict[str, object]] = []
    for item in raw:
        reviewer = jsonio.as_object(value=item)
        if reviewer is not None:
            reviewers.append(reviewer)
    return reviewers


def model_for(*, reviewer_id: str) -> dict[str, str] | None:
    for identity in MODEL_IDENTITIES:
        if identity["reviewer_id"] == reviewer_id:
            return identity
    return None


def typed_action(*, action: object) -> dict[str, object] | None:
    payload = jsonio.as_object(value=action)
    if payload is None:
        return None
    action_id = payload.get("action_id")
    params = payload.get("params")
    if not isinstance(action_id, str) or action_id not in ACTION_ID_SET:
        return None
    if jsonio.as_object(value=params) is None:
        return None
    return {"action_id": action_id, "params": params}


def review_record(*, reviewer: dict[str, object]) -> dict[str, object]:
    reviewer_id = str_field(payload=reviewer, key="reviewer_id")
    return {
        "reviewer_id": reviewer_id,
        "model": model_for(reviewer_id=reviewer_id),
        "verdict": reviewer.get("verdict"),
        "action": reviewer.get("action"),
    }


def escalation(
    *, reason: str, request: dict[str, object], reviewers: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "escalate",
        "reason": reason,
        "action": {"action_id": "human_valve", "params": {}},
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request),
        "mutated": False,
    }


def unanimous(
    *, action: dict[str, object], request: dict[str, object], reviewers: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "unanimous",
        "reason": "three_typed_actions_equal",
        "action": action,
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request),
        "mutated": False,
    }


def dissent_result(
    *, request: dict[str, object], reviewers: list[dict[str, object]], dissent: dict[str, object]
) -> dict[str, object]:
    result = escalation(
        reason="non_anthropic_needs_human_dissent", request=request, reviewers=reviewers
    )
    result["dissent"] = review_record(reviewer=dissent)
    return result


def reviewer_escalation_reason(*, reviewer: dict[str, object]) -> str | None:
    reviewer_id = str_field(payload=reviewer, key="reviewer_id")
    identity = model_for(reviewer_id=reviewer_id)
    if identity is None:
        return "unpinned_model_identity"
    verdict = reviewer.get("verdict")
    action = typed_action(action=reviewer.get("action"))
    if verdict == "insufficient-information":
        return "insufficient_information"
    if action is None:
        return "free_form_action"
    if verdict == "needs-human":
        return (
            "non_anthropic_needs_human_dissent"
            if identity["vendor"] != "anthropic"
            else "needs_human"
        )
    return None if verdict == "unblock" else "unknown_verdict"


def evaluate_verdicts(
    *, request: dict[str, object], responses: dict[str, object]
) -> dict[str, object]:
    reviewers = reviewers_from(responses=responses)
    result: dict[str, object] | None = None
    if len(reviewers) != len(MODEL_IDENTITIES):
        result = escalation(reason="panel_size_mismatch", request=request, reviewers=reviewers)
    actions: list[dict[str, object]] = []
    for reviewer in reviewers if result is None else []:
        reason = reviewer_escalation_reason(reviewer=reviewer)
        if reason == "non_anthropic_needs_human_dissent":
            result = dissent_result(request=request, reviewers=reviewers, dissent=reviewer)
            continue
        if reason is not None:
            result = escalation(reason=reason, request=request, reviewers=reviewers)
            continue
        action = typed_action(action=reviewer.get("action"))
        if action is not None:  # pragma: no branch
            actions.append(action)
    if result is None:
        canonical = {canonical_json(value=action) for action in actions}
        result = (
            unanimous(action=actions[0], request=request, reviewers=reviewers)
            if len(canonical) == 1
            else escalation(
                reason="typed_action_disagreement", request=request, reviewers=reviewers
            )
        )
    return result
