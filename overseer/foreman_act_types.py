"""Shared type and action-id constants for foreman lifecycle acts."""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

__all__: list[str] = [
    "ACTION_IDS",
    "BLOCKED_SESSION_ANSWER",
    "DISPATCH_JOURNAL_RECONCILE_MERGED",
    "FOREMAN_EPIC_CREATE",
    "HUMAN_VALVE",
    "PLAN_START",
    "PROPOSAL_SCHEMA_VERSION",
    "QUALIFYING_SESSION_RESUME",
    "QUALIFYING_SESSION_START",
    "SUPERVISOR_PAIR_START",
    "WORK_ITEM_COMMENT",
    "WORK_ITEM_FILE",
    "WORK_ITEM_SESSION_ACTIONS",
    "WORK_ITEM_SESSION_FINISH",
    "WORK_ITEM_SESSION_RESUME",
    "WORK_ITEM_SESSION_START",
    "WORK_ITEM_UPDATE",
    "ActResult",
    "ActionId",
]

PROPOSAL_SCHEMA_VERSION: Final[int] = 1

ActionId: TypeAlias = Literal[
    "blocked_session_answer",
    "dispatch_journal_reconcile_merged",
    "foreman_epic_create",
    "human_valve",
    "plan_start",
    "qualifying_session_resume",
    "qualifying_session_start",
    "supervisor_pair_start",
    "work_item_comment",
    "work_item_file",
    "work_item_update",
    "work_item_session_finish",
    "work_item_session_resume",
    "work_item_session_start",
]
ActResult: TypeAlias = dict[str, object]

BLOCKED_SESSION_ANSWER: Final[ActionId] = "blocked_session_answer"
DISPATCH_JOURNAL_RECONCILE_MERGED: Final[ActionId] = "dispatch_journal_reconcile_merged"
FOREMAN_EPIC_CREATE: Final[ActionId] = "foreman_epic_create"
HUMAN_VALVE: Final[ActionId] = "human_valve"
PLAN_START: Final[ActionId] = "plan_start"
QUALIFYING_SESSION_RESUME: Final[ActionId] = "qualifying_session_resume"
QUALIFYING_SESSION_START: Final[ActionId] = "qualifying_session_start"
SUPERVISOR_PAIR_START: Final[ActionId] = "supervisor_pair_start"
WORK_ITEM_COMMENT: Final[ActionId] = "work_item_comment"
WORK_ITEM_FILE: Final[ActionId] = "work_item_file"
WORK_ITEM_UPDATE: Final[ActionId] = "work_item_update"
WORK_ITEM_SESSION_FINISH: Final[ActionId] = "work_item_session_finish"
WORK_ITEM_SESSION_RESUME: Final[ActionId] = "work_item_session_resume"
WORK_ITEM_SESSION_START: Final[ActionId] = "work_item_session_start"
WORK_ITEM_SESSION_ACTIONS: Final[tuple[ActionId, ...]] = (
    WORK_ITEM_SESSION_FINISH,
    WORK_ITEM_SESSION_RESUME,
    WORK_ITEM_SESSION_START,
)

ACTION_IDS: Final[tuple[ActionId, ...]] = (
    BLOCKED_SESSION_ANSWER,
    DISPATCH_JOURNAL_RECONCILE_MERGED,
    FOREMAN_EPIC_CREATE,
    HUMAN_VALVE,
    PLAN_START,
    QUALIFYING_SESSION_RESUME,
    QUALIFYING_SESSION_START,
    SUPERVISOR_PAIR_START,
    WORK_ITEM_COMMENT,
    WORK_ITEM_FILE,
    WORK_ITEM_UPDATE,
    WORK_ITEM_SESSION_FINISH,
    WORK_ITEM_SESSION_RESUME,
    WORK_ITEM_SESSION_START,
)
