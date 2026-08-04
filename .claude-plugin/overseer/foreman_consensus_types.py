"""Shared constants and typed limits for the Phase C consensus panel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TypeAlias

from foreman_act_types import ActionId

__all__: list[str] = [
    "CACHE_TTL_SECONDS",
    "DEFAULT_CONCURRENCY_CAP",
    "DEFAULT_DAILY_PANEL_BUDGET",
    "DEFAULT_PANEL_LIMITS",
    "DEFAULT_PER_TICK_PANEL_BUDGET",
    "DEFAULT_STATE_DIR",
    "MODEL_IDENTITIES",
    "PANEL_SCHEMA_VERSION",
    "POLICY_VERSION",
    "PROMPT_VERSION",
    "PanelLimits",
    "TypedAction",
    "VerdictKind",
]

PANEL_SCHEMA_VERSION: Final[int] = 1
POLICY_VERSION: Final[str] = "phase-c-report-only-v1"
PROMPT_VERSION: Final[str] = "phase-c-reviewer-prompt-v1"
CACHE_TTL_SECONDS: Final[int] = 86_400
DEFAULT_PER_TICK_PANEL_BUDGET: Final[int] = 1
DEFAULT_DAILY_PANEL_BUDGET: Final[int] = 24
DEFAULT_CONCURRENCY_CAP: Final[int] = 1
DEFAULT_STATE_DIR: Final[Path] = Path("tmp/overseer/foreman")

VerdictKind: TypeAlias = Literal["unblock", "needs-human", "insufficient-information"]
TypedAction: TypeAlias = dict[str, object]

MODEL_IDENTITIES: Final[tuple[dict[str, str], ...]] = (
    {
        "reviewer_id": "fable",
        "vendor": "anthropic",
        "model": "claude-fable-5-20260804",
    },
    {
        "reviewer_id": "gemini",
        "vendor": "google",
        "model": "gemini-2.5-pro-20250617",
    },
    {
        "reviewer_id": "gpt",
        "vendor": "openai",
        "model": "gpt-5-codex-20260804",
    },
)

ACTION_ID_SET: Final[frozenset[ActionId]] = frozenset(
    {
        "blocked_session_answer",
        "dispatch_journal_reconcile_merged",
        "human_valve",
        "plan_start",
        "qualifying_session_resume",
        "qualifying_session_start",
        "supervisor_pair_start",
        "work_item_file",
        "work_item_session_finish",
        "work_item_session_resume",
        "work_item_session_start",
    }
)


@dataclass(frozen=True, kw_only=True)
class PanelLimits:
    per_tick_panel_budget: int = DEFAULT_PER_TICK_PANEL_BUDGET
    daily_panel_budget: int = DEFAULT_DAILY_PANEL_BUDGET
    concurrency_cap: int = DEFAULT_CONCURRENCY_CAP


DEFAULT_PANEL_LIMITS: Final[PanelLimits] = PanelLimits()
