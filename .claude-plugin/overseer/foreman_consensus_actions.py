"""Typed reviewer action helpers for the foreman consensus matrix."""

from __future__ import annotations

import jsonio
from foreman_consensus_prompt import str_field
from foreman_consensus_types import ACTION_ID_SET, MODEL_IDENTITIES

__all__: list[str] = [
    "action_is_reversible",
    "action_is_rollback_bounded",
    "model_for",
    "review_record",
    "typed_action",
]


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
    result = {
        "reviewer_id": reviewer_id,
        "model": model_for(reviewer_id=reviewer_id),
        "verdict": reviewer.get("verdict"),
        "action": reviewer.get("action"),
    }
    if "hard_risk" in reviewer:
        result["hard_risk"] = reviewer.get("hard_risk")
    if "risk_kind" in reviewer:
        result["risk_kind"] = reviewer.get("risk_kind")
    return result
