"""Early refusal checks for foreman panel requests."""

from __future__ import annotations

import re
from typing import Final

__all__: list[str] = [
    "refusal_for",
    "refused_result",
]

REQUIRED_REQUEST_FIELDS: Final[tuple[str, ...]] = (
    "blocked_question",
    "handoff_or_work_item",
    "repo",
    "repo_context",
    "topic",
)
HINT_REASONS: Final[tuple[tuple[str, str], ...]] = (
    ("unanimous", "verdict_hint_in_blocked_question"),
    ("unblock", "verdict_hint_in_blocked_question"),
    ("needs-human", "verdict_hint_in_blocked_question"),
    ("insufficient-information", "verdict_hint_in_blocked_question"),
    ("escalate", "verdict_hint_in_blocked_question"),
    ("human_valve", "verdict_hint_in_blocked_question"),
)


def str_field(*, payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def refused_result(*, reason: str) -> dict[str, object]:
    return {"outcome": "refused", "reason": reason, "reviewers": []}


def hint_match(*, question: str, token: str) -> re.Match[str] | None:
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", question)


def refusal_for(*, request: dict[str, object]) -> dict[str, object] | None:
    missing_fields = [
        field for field in REQUIRED_REQUEST_FIELDS if str_field(payload=request, key=field) == ""
    ]
    if len(missing_fields) == len(REQUIRED_REQUEST_FIELDS):
        result = refused_result(reason="missing_required_request_fields")
        result["missing_fields"] = missing_fields
        return result
    question = str_field(payload=request, key="blocked_question").lower()
    for token, reason in HINT_REASONS:
        match = hint_match(question=question, token=token)
        if match is not None:
            result = refused_result(reason=reason)
            result["hint"] = {"token": token, "offset": match.start()}
            return result
    return None
