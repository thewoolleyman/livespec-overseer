"""NEEDS YOU presentation rendering for report-only consensus outcomes."""

from __future__ import annotations

import jsonio
from foreman_consensus_prompt import str_field

__all__: list[str] = [
    "presentation",
]


def tmux_session(*, request: dict[str, object]) -> str:
    direct = str_field(payload=request, key="tmux")
    if direct:
        return direct
    snapshot = jsonio.as_object(value=request.get("snapshot")) or {}
    for key in ("tmux", "session_name"):
        value = snapshot.get(key)
        if isinstance(value, str) and value:
            return value
    return str_field(payload=request, key="topic")


def reviewer_summary(*, reviewer: dict[str, object]) -> dict[str, object]:
    action = jsonio.as_object(value=reviewer.get("action"))
    action_id = action.get("action_id") if action is not None else "untyped"
    rationale = str_field(payload=reviewer, key="rationale")
    verdict = reviewer.get("verdict")
    return {
        "reviewer_id": str_field(payload=reviewer, key="reviewer_id"),
        "verdict": verdict,
        "action_id": action_id if isinstance(action_id, str) else "untyped",
        "summary": rationale or f"{verdict} via {action_id}",
    }


def presentation(
    *, request: dict[str, object], reviewers: list[dict[str, object]], action: dict[str, object]
) -> dict[str, object]:
    return {
        "surface": "NEEDS YOU",
        "tmux": tmux_session(request=request),
        "updated_choice": {
            "action_id": action["action_id"],
            "label": "Ask the human",
            "description": "Present the reviewer summaries before asking for a choice.",
        },
        "reviewers": [reviewer_summary(reviewer=reviewer) for reviewer in reviewers],
    }
