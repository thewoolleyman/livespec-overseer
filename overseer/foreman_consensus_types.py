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
    "DecisionRule",
    "PanelLimits",
    "TypedAction",
    "VerdictKind",
    "construct_model_identities",
]

PANEL_SCHEMA_VERSION: Final[int] = 1
POLICY_VERSION: Final[str] = "phase-c-report-only-v1"
PROMPT_VERSION: Final[str] = "phase-c-reviewer-prompt-v3"
CACHE_TTL_SECONDS: Final[int] = 86_400
DEFAULT_PER_TICK_PANEL_BUDGET: Final[int] = 1
DEFAULT_DAILY_PANEL_BUDGET: Final[int] = 24
DEFAULT_CONCURRENCY_CAP: Final[int] = 1
DEFAULT_STATE_DIR: Final[Path] = Path("tmp/overseer/foreman")

VerdictKind: TypeAlias = Literal["unblock", "needs-human", "insufficient-information"]
DecisionRule: TypeAlias = Literal["unanimous", "majority"]
TypedAction: TypeAlias = dict[str, object]
ModelIdentity: TypeAlias = dict[str, str]

VERIFIED_MODEL_RESOLUTIONS: Final[dict[tuple[str, str], str]] = {
    ("anthropic", "claude-fable-5"): "anthropic/claude-fable-5",
    ("anthropic", "claude-opus-5"): "anthropic/claude-opus-5",
    ("anthropic", "claude-sonnet-5"): "anthropic/claude-sonnet-5",
    ("openai", "gpt-5.6-sol"): "openai/gpt-5.6-sol",
}


def resolved_model_identity(*, identity: ModelIdentity) -> str:
    reviewer_id = identity["reviewer_id"]
    vendor = identity["vendor"]
    model = identity["model"]
    resolved = VERIFIED_MODEL_RESOLUTIONS.get((vendor, model))
    if resolved is None:
        msg = f"unresolvable pinned model identity for reviewer {reviewer_id}: {vendor}/{model}"
        raise ValueError(msg)
    return resolved


def require_one_non_anthropic(*, identities: tuple[ModelIdentity, ...]) -> None:
    non_anthropic_count = sum(1 for identity in identities if identity["vendor"] != "anthropic")
    if non_anthropic_count != 1:
        msg = "consensus panel must have exactly one non-Anthropic reviewer"
        raise ValueError(msg)


def construct_model_identities(
    *, identities: tuple[ModelIdentity, ...]
) -> tuple[ModelIdentity, ...]:
    resolved_models: set[str] = set()
    constructed: list[ModelIdentity] = []
    for identity in identities:
        resolved_model = resolved_model_identity(identity=identity)
        if resolved_model in resolved_models:
            msg = f"duplicate resolved model identity: {resolved_model}"
            raise ValueError(msg)
        resolved_models.add(resolved_model)
        constructed.append(dict(identity))
    result = tuple(constructed)
    require_one_non_anthropic(identities=result)
    return result


MODEL_IDENTITIES: Final[tuple[ModelIdentity, ...]] = construct_model_identities(
    identities=(
        {
            "reviewer_id": "fable",
            "vendor": "anthropic",
            "model": "claude-fable-5",
        },
        {
            "reviewer_id": "opus",
            "vendor": "anthropic",
            "model": "claude-opus-5",
        },
        {
            "reviewer_id": "gpt-sol",
            "vendor": "openai",
            "model": "gpt-5.6-sol",
        },
    )
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
