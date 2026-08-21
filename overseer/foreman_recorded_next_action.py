"""The recorded-next-action carve-out for gated blocked-session answers.

A picker option that restates the plan's own ledger-recorded next action is not
a decision the panel needs to make; the decision was already made and written
down. Requiring consensus evidence for it parks the session on its own recorded
instruction, measured at sixteen hours on the rop-railway picker.

This module decides only whether that carve-out APPLIES. It removes the
requirement for panel evidence and nothing else: the valve disposition gate and
the hard floors are evaluated by the caller exactly as before.
"""

from __future__ import annotations

import re

import jsonio
from foreman_act_types import BLOCKED_SESSION_ANSWER

__all__: list[str] = [
    "EMITTING_PLAN_PRIMITIVE_NEXT_ACTION_PHRASE",
    "RecordedNextAction",
    "next_actions",
    "recorded_next_action_authorization",
]

EMITTING_PLAN_PRIMITIVE_NEXT_ACTION_PHRASE = "opening handoff with exactly one next action"
PLAN_PRIMITIVE_NEXT_ACTION_HEADING_LABEL = " ".join(
    EMITTING_PLAN_PRIMITIVE_NEXT_ACTION_PHRASE.split()[-2:]
).upper()

_LEGACY_NEXT_ACTION = re.compile(
    rf"^\s*{re.escape(PLAN_PRIMITIVE_NEXT_ACTION_HEADING_LABEL)}\b[^:]*:\s*" r"(?P<action>.+?)\s*$",
    re.IGNORECASE,
)
_MARKDOWN_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$")
_NEXT_ACTION_HEADING = re.compile(
    rf"(?m)^\s{{0,3}}#{{1,6}}\s+"
    rf"(?:.+\s+)?{re.escape(PLAN_PRIMITIVE_NEXT_ACTION_HEADING_LABEL)}\b"
    r"(?:\s*\([^)]*\))?\s*$",
    re.IGNORECASE,
)


class RecordedNextAction:
    """The matched next action and the record of where it was read from."""

    def __init__(self, *, matched_text: str, source: str) -> None:
        self.matched_text = matched_text
        self.source = source


def _payload(*, proposal: dict[str, object]) -> dict[str, object] | None:
    return jsonio.as_object(value=proposal.get("recorded_next_action"))


def _text_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value.strip() != "" else None


def _answer_text(*, proposal: dict[str, object]) -> str | None:
    answer = jsonio.as_object(value=proposal.get(BLOCKED_SESSION_ANSWER))
    if answer is None:  # pragma: no cover
        return None
    return _text_field(payload=answer, key="answer_text")


def normalized(*, text: str) -> str:
    """Compare on words, not on typography.

    A picker renders its options with its own capitalization and trailing
    punctuation; the handoff writes prose. Neither difference makes the option a
    different instruction, and neither may be allowed to widen the match beyond
    the words themselves.
    """
    collapsed = " ".join(text.split())
    return collapsed.strip().strip(".").casefold()


def next_actions(*, handoff_text: str) -> list[str]:
    legacy_actions = [
        match.group("action")
        for line in handoff_text.splitlines()
        if (match := _LEGACY_NEXT_ACTION.match(line)) is not None
    ]
    heading_actions: list[str] = []
    for match in _NEXT_ACTION_HEADING.finditer(handoff_text):
        section = handoff_text[match.end() :]
        next_heading = _MARKDOWN_HEADING.search(section)
        body = section[: next_heading.start() if next_heading is not None else len(section)]
        body_actions = [line.strip() for line in body.splitlines() if line.strip()]
        heading_actions.extend(body_actions[:1])
    return legacy_actions + heading_actions


def recorded_next_action_authorization(
    *, proposal: dict[str, object]
) -> tuple[RecordedNextAction | None, str | None]:
    """Return the matched next action, or a refusal, or neither.

    Neither — ``(None, None)`` — means the carve-out was not claimed and the
    caller must fall through to the consensus path. A refusal is returned only
    when the carve-out WAS claimed and does not hold, so a foreman that attaches
    a handoff cannot have the claim quietly ignored.
    """
    payload = _payload(proposal=proposal)
    if payload is None:
        return None, None
    handoff_text = _text_field(payload=payload, key="handoff_text")
    source = _text_field(payload=payload, key="source")
    answer_text = _answer_text(proposal=proposal)
    if handoff_text is None or source is None or answer_text is None:
        return None, "malformed_recorded_next_action"
    actions = next_actions(handoff_text=handoff_text)
    if len(actions) != 1:
        return None, "recorded_next_action_not_singular"
    matched = normalized(text=actions[0])
    if normalized(text=answer_text) != matched:
        # Not a refusal: the option simply is not the recorded action, so the
        # ordinary consensus path decides it. Refusing here would make a
        # correctly-attached handoff worse than none at all.
        return None, None
    return RecordedNextAction(matched_text=matched, source=source), None
