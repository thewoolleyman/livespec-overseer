"""Determine the UNROUTED-PLAN condition and identify its enumerated remedy.

The condition is the three-way conjunction the ratified contract states: a plan
is UNROUTED when it is unactioned past its bound, its ready work is aging, and
no live session is working it. Every input arrives already measured — the
past-bound verdict from `foreman_unrouted_plan_bound`, the other two projected
out of the attention view the foreman composes — so the determination made here
is a total function of those inputs and rests on no judgement of its own. Each
result carries the `inputs` it was computed from, so a reader who did not
perform the determination can re-check it without re-reading this module.

The result is THREE-VALUED and fails closed. Any required input the view does
not carry resolves the condition UNDETERMINED and names the missing input,
because an unavailable input is not evidence that a plan is being worked; an
UNDETERMINED condition therefore never renders as the ABSENT that a determined,
not-in-condition plan carries.

Where the condition HOLDS the remedy is read from a CLOSED mapping over the
session states, whose values are the session-lifecycle acts the DELEGATION FLOOR
enumerates: getting a worker started where a plan has none, resuming the session
of a plan that has one, and answering the gate parking a supervised pane. The
mapping is total over every session state other than `working` — which is
precisely the state in which the condition cannot hold — so a plan in the
condition always has an enumerated remedy, and the foreman never reaches the
position of having to escalate for want of one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import jsonio
from foreman_act_types import (
    BLOCKED_SESSION_ANSWER,
    PLAN_START,
    QUALIFYING_SESSION_RESUME,
    ActionId,
)
from foreman_unrouted_plan_bound import UNDETERMINED

__all__: list[str] = [
    "ABSENT",
    "ATTENTION_VIEW_UNAVAILABLE",
    "HOLDS",
    "PAST_BOUND_UNDETERMINED",
    "REMEDY_BY_SESSION_STATE",
    "SESSION_STATE_UNAVAILABLE",
    "SESSION_WORKING",
    "UNDETERMINED",
    "PlanAttentionFacts",
    "UnroutedPlanCondition",
    "annotate_unrouted_plan_condition",
    "plan_attention_facts",
    "unrouted_plan_condition",
]

HOLDS: Final[str] = "holds"
ABSENT: Final[str] = "absent"
ATTENTION_VIEW_UNAVAILABLE: Final[str] = "attention_view_unavailable"
SESSION_STATE_UNAVAILABLE: Final[str] = "session_state_unavailable"
PAST_BOUND_UNDETERMINED: Final[str] = "unactioned_past_bound_undetermined"
SESSION_WORKING: Final[str] = "working"
# The closed session-lifecycle remedy mapping. Every value is one of the
# unsticking acts the DELEGATION FLOOR enumerates; `working` is deliberately
# absent because the condition cannot hold while a live session works the plan.
REMEDY_BY_SESSION_STATE: Final[dict[str, ActionId]] = {
    "done-ready-to-archive": QUALIFYING_SESSION_RESUME,
    "idle": QUALIFYING_SESSION_RESUME,
    "no-session": PLAN_START,
    "picker-parked": BLOCKED_SESSION_ANSWER,
}
_ATTRIBUTION_KEYS: Final[tuple[str, ...]] = ("plan", "tmux", "session_name")
_ROW_CONDITION_KEY: Final[str] = "unrouted_plan_condition"
_ROW_INPUTS_KEY: Final[str] = "unrouted_plan_condition_inputs"
_ROW_PLAN_KEY: Final[str] = "plan"
_ROW_REASONS_KEY: Final[str] = "unrouted_plan_condition_undetermined_reasons"
_ROW_REMEDY_KEY: Final[str] = "unrouted_plan_remedy"
_ROW_SESSION_STATE_KEY: Final[str] = "session_state"
_ROW_VERDICT_KEY: Final[str] = "unactioned_past_bound"
_ROW_VERDICT_REASON_KEY: Final[str] = "unactioned_past_bound_undetermined_reason"


@dataclass(frozen=True, kw_only=True)
class PlanAttentionFacts:
    """The per-plan facts the attention view carries, or None where it does not."""

    ready_work_aging: bool | None
    session_state: str | None


@dataclass(frozen=True, kw_only=True)
class UnroutedPlanCondition:
    """A three-valued condition, the remedy it identifies, and its own inputs."""

    condition: str
    inputs: dict[str, object]
    remedy: ActionId | None
    undetermined_reasons: tuple[str, ...]

    def document(self) -> dict[str, object]:
        return {
            _ROW_CONDITION_KEY: self.condition,
            _ROW_INPUTS_KEY: self.inputs,
            _ROW_REASONS_KEY: list(self.undetermined_reasons),
            _ROW_REMEDY_KEY: self.remedy,
        }


def _attention_items(*, attention: dict[str, object] | None) -> list[dict[str, object]] | None:
    """Parse the view's items, distinguishing an ABSENT view from an EMPTY one."""
    if attention is None:
        return None
    raw_items = jsonio.as_list(value=attention.get("items"))
    if raw_items is None:
        return None
    return [item for item in (jsonio.as_object(value=raw) for raw in raw_items) if item is not None]


def _attributed_to_plan(*, item: dict[str, object], plan: str) -> bool:
    return any(item.get(key) == plan for key in _ATTRIBUTION_KEYS)


def plan_attention_facts(
    *, plan: object, attention: dict[str, object] | None, session_state: object
) -> PlanAttentionFacts:
    """Project the per-plan facts the condition reads out of the attention view."""
    items = _attention_items(attention=attention)
    ready_work_aging = (
        None
        if items is None or not isinstance(plan, str)
        else any(_attributed_to_plan(item=item, plan=plan) for item in items)
    )
    return PlanAttentionFacts(
        ready_work_aging=ready_work_aging,
        session_state=session_state if isinstance(session_state, str) else None,
    )


def _undetermined_reasons(
    *,
    facts: PlanAttentionFacts,
    past_bound: bool | None,
    past_bound_reason: str | None,
    remedy: ActionId | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if past_bound is None:
        reasons.append(PAST_BOUND_UNDETERMINED if past_bound_reason is None else past_bound_reason)
    if facts.ready_work_aging is None:
        reasons.append(ATTENTION_VIEW_UNAVAILABLE)
    if remedy is None and facts.session_state != SESSION_WORKING:
        reasons.append(SESSION_STATE_UNAVAILABLE)
    return tuple(reasons)


def unrouted_plan_condition(
    *,
    facts: PlanAttentionFacts,
    unactioned_past_bound: bool | str,
    unactioned_past_bound_undetermined_reason: str | None = None,
) -> UnroutedPlanCondition:
    """Resolve the condition as a total function of the facts and the count verdict."""
    past_bound = unactioned_past_bound if isinstance(unactioned_past_bound, bool) else None
    remedy = (
        None if facts.session_state is None else REMEDY_BY_SESSION_STATE.get(facts.session_state)
    )
    inputs: dict[str, object] = {
        "ready_work_aging": facts.ready_work_aging,
        "session_state": facts.session_state,
        "unactioned_past_bound": unactioned_past_bound,
    }
    reasons = _undetermined_reasons(
        facts=facts,
        past_bound=past_bound,
        past_bound_reason=unactioned_past_bound_undetermined_reason,
        remedy=remedy,
    )
    if reasons:
        return UnroutedPlanCondition(
            condition=UNDETERMINED,
            inputs=inputs,
            remedy=None,
            undetermined_reasons=reasons,
        )
    if past_bound and facts.ready_work_aging and remedy is not None:
        return UnroutedPlanCondition(
            condition=HOLDS,
            inputs=inputs,
            remedy=remedy,
            undetermined_reasons=(),
        )
    return UnroutedPlanCondition(
        condition=ABSENT,
        inputs=inputs,
        remedy=None,
        undetermined_reasons=(),
    )


def _row_verdict_reason(*, row: dict[str, object]) -> str | None:
    reason = row.get(_ROW_VERDICT_REASON_KEY)
    return reason if isinstance(reason, str) else None


def _row_verdict(*, row: dict[str, object]) -> bool | str:
    verdict = row.get(_ROW_VERDICT_KEY)
    return verdict if isinstance(verdict, bool | str) else UNDETERMINED


def annotate_unrouted_plan_condition(
    *, rows: list[dict[str, object]], attention: dict[str, object] | None
) -> dict[str, object]:
    """Annotate each roster row with its condition; return the view's own document."""
    items = _attention_items(attention=attention)
    for row in rows:
        resolved = unrouted_plan_condition(
            facts=plan_attention_facts(
                plan=row.get(_ROW_PLAN_KEY),
                attention=attention,
                session_state=row.get(_ROW_SESSION_STATE_KEY),
            ),
            unactioned_past_bound=_row_verdict(row=row),
            unactioned_past_bound_undetermined_reason=_row_verdict_reason(row=row),
        )
        row.update(resolved.document())
    return {
        "available": items is not None,
        "item_count": None if items is None else len(items),
        "undetermined_reason": None if items is not None else ATTENTION_VIEW_UNAVAILABLE,
    }
