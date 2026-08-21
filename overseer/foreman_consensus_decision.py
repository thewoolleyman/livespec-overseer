"""Consensus-panel decision matrix and reviewer validation helpers."""

from __future__ import annotations

import jsonio
from foreman_consensus_present import presentation
from foreman_consensus_prompt import cache_key, canonical_json, str_field
from foreman_consensus_types import ACTION_ID_SET, MODEL_IDENTITIES, PANEL_SCHEMA_VERSION

_ONE = 1
_TWO = 2

__all__: list[str] = [
    "decision_matrix_result",
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


def action_is_reversible(*, action: object) -> bool:
    payload = jsonio.as_object(value=action)
    return payload is not None and payload.get("reversible") is True


def action_is_rollback_bounded(*, action: object) -> bool:
    payload = jsonio.as_object(value=action) or {}
    rollback = jsonio.as_object(value=payload.get("rollback"))
    return payload.get("rollback_bounded") is True or (
        rollback is not None and rollback.get("bounded") is True
    )


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
    action: dict[str, object] = {"action_id": "human_valve", "params": {}}
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "escalate",
        "reason": reason,
        "action": action,
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "presentation": presentation(request=request, reviewers=reviewers, action=action),
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
) -> dict[str, object]:
    round_held = held_reviewer_ids(
        responses=responses,
        required={str_field(payload=reviewer, key="reviewer_id") for reviewer in unblockers},
    )
    if round_held is None:
        return escalation(reason="needs_human", request=request, reviewers=reviewers)
    if not action_is_reversible(action=unblockers[0].get("action")):
        return escalation(
            reason="minority_action_not_reversible", request=request, reviewers=reviewers
        )
    if not action_is_rollback_bounded(action=unblockers[0].get("action")):
        return escalation(
            reason="minority_action_not_rollback_bounded", request=request, reviewers=reviewers
        )
    if not round_held:
        return escalation(reason="minority_report_not_held", request=request, reviewers=reviewers)
    action = typed_action(action=unblockers[0].get("action")) or {}
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "minority_override",
        "reason": "minority_report_both_holders_confirmed",
        "action": action,
        "dissent": review_record(reviewer=dissent),
        "minority_report_round": {"held_by": round_held},
        "reviewers": [review_record(reviewer=reviewer) for reviewer in reviewers],
        "models": MODEL_IDENTITIES,
        "cache_key": cache_key(request=request),
        "mutated": False,
    }


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


def decision_matrix_result(
    *,
    request: dict[str, object],
    responses: dict[str, object],
    reviewers: list[dict[str, object]],
    needs_human: list[dict[str, object]],
    unblockers: list[dict[str, object]],
    actions: list[dict[str, object]],
) -> dict[str, object]:
    canonical = {canonical_json(value=action) for action in actions}
    unblocker_canonical = {
        canonical_json(value=typed_action(action=reviewer.get("action")) or {})
        for reviewer in unblockers
    }
    if not needs_human and len(canonical) == _ONE:
        return unanimous(action=actions[0], request=request, reviewers=reviewers)
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
