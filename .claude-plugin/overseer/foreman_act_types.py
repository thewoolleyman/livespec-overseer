"""Shared type and action-id constants for foreman lifecycle acts."""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

__all__: list[str] = [
    "ACTION_IDS",
    "BLOCKED_SESSION_ANSWER",
    "HUMAN_VALVE",
    "PLAN_START",
    "PROPOSAL_SCHEMA_VERSION",
    "QUALIFYING_SESSION_RESUME",
    "QUALIFYING_SESSION_START",
    "SUPERVISOR_PAIR_START",
    "ActResult",
    "ActionId",
]

PROPOSAL_SCHEMA_VERSION: Final[int] = 1

ActionId: TypeAlias = Literal[
    "blocked_session_answer",
    "human_valve",
    "plan_start",
    "qualifying_session_resume",
    "qualifying_session_start",
    "supervisor_pair_start",
]
ActResult: TypeAlias = dict[str, object]

BLOCKED_SESSION_ANSWER: Final[ActionId] = "blocked_session_answer"
HUMAN_VALVE: Final[ActionId] = "human_valve"
PLAN_START: Final[ActionId] = "plan_start"
QUALIFYING_SESSION_RESUME: Final[ActionId] = "qualifying_session_resume"
QUALIFYING_SESSION_START: Final[ActionId] = "qualifying_session_start"
SUPERVISOR_PAIR_START: Final[ActionId] = "supervisor_pair_start"

ACTION_IDS: Final[tuple[ActionId, ...]] = (
    BLOCKED_SESSION_ANSWER,
    HUMAN_VALVE,
    PLAN_START,
    QUALIFYING_SESSION_RESUME,
    QUALIFYING_SESSION_START,
    SUPERVISOR_PAIR_START,
)
