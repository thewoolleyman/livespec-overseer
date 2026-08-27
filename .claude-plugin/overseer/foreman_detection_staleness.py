"""Route a surfaced DETECTION-STALENESS item, and never run the detection.

Ratified by v035 in `SPECIFICATION/spec.md`, in its relay and escalation floors:
where the attention view surfaces a DETECTION-STALENESS item — a report that a
convergence detection is overdue — the foreman MUST treat it as a ROUTING
target, routing it to an attended session for the owning plan or to the grooming
operation. It MUST NOT run the detection itself, and MUST NOT treat the item as
satisfied by any act other than that routing.

WHY ROUTING IS THE ONLY CORRECT RESPONSE. The detections that keep specification
and implementation converging are consent-gated attended dialogues by design:
each finding is offered to a human, one at a time. An unattended surface that
ran one would either bypass that consent or stall holding a dialogue nobody is
present for, and both outcomes are worse than not running it. At the same time,
an item reporting that detection is overdue is exactly the kind of fact this
loop exists to act on, so an unattended surface that receives one and does
nothing reproduces the ownership hole the item was composed to close. Routing is
what is left, and it is the whole of what this module does.

THE SURFACE CANNOT RUN A DETECTION, AND THAT IS STRUCTURAL RATHER THAN STATED.
This module imports no execution primitive — no subprocess, no os-level spawn,
no command runner — so there is no path from a surfaced item to running
anything. What it emits instead is a ROUTING record naming a target and, where
the attended session must first be started or resumed, the session-lifecycle act
the DELEGATION FLOOR already enumerates for that plan's session state. That act
is read from the SAME closed mapping the tick's unrouted-plan determination
uses, so a routing never names a target the rest of the tick would not
recognise, and the act vocabulary stays the one closed enumeration — which
carries no detection-running act at all.

ROUTING IS TOTAL AND FAILS TOWARD THE GROOMING OPERATION. An item the view
attributes to no plan, to a plan this roster does not carry, or to a plan whose
session state this roster cannot read is routed to the grooming operation, whose
drain pass is where detection staleness is checked. An unreadable session state
is not evidence that someone is attending the plan, so it resolves to the
standing operation rather than to no target: nothing is dropped for want of an
owning plan, and nothing is ever answered by running the detection instead.

SATISFACTION IS NARROW ON PURPOSE. Only a routing act naming the item and one of
the two enumerated targets discharges it; every other act — a comment, a
work-item update, and in particular an act claiming the detection was run —
leaves the item OUTSTANDING. A wider reading would let this surface mark the
item done by doing the one thing the clause forbids.

Recognizing WHICH surfaced items are detection-staleness reports is the separate
concern of `foreman_detection_staleness_items`, whose vocabulary this module
re-exports so a caller has one surface to import.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _signals_topics import grooming_topic
from foreman_act_types import ActionId
from foreman_detection_staleness_items import (
    DETECTION_STALENESS_KIND,
    UNIDENTIFIED_ITEM_ID,
    DetectionStalenessItem,
    detection_kind,
    detection_staleness_items,
    is_detection_staleness,
    kind_slug,
)
from foreman_unrouted_plan_condition import (
    ATTENTION_VIEW_UNAVAILABLE,
    REMEDY_BY_SESSION_STATE,
    SESSION_WORKING,
)

__all__: list[str] = [
    "ATTENDED_PLAN_SESSION",
    "ATTENTION_VIEW_UNAVAILABLE",
    "DETECTION_STALENESS_KIND",
    "GROOMING_OPERATION",
    "OUTSTANDING",
    "ROUTED",
    "ROUTING_ACT_KIND",
    "ROUTING_TARGETS",
    "UNIDENTIFIED_ITEM_ID",
    "DetectionStalenessItem",
    "DetectionStalenessRouting",
    "act_routes_item",
    "detection_kind",
    "detection_staleness_document",
    "detection_staleness_items",
    "is_detection_staleness",
    "kind_slug",
    "route_item",
    "satisfaction",
    "session_states_by_plan",
]

ATTENDED_PLAN_SESSION: Final[str] = "attended-plan-session"
GROOMING_OPERATION: Final[str] = "grooming-operation"
ROUTING_TARGETS: Final[tuple[str, str]] = (ATTENDED_PLAN_SESSION, GROOMING_OPERATION)
ROUTING_ACT_KIND: Final[str] = "detection-staleness-routing"
ROUTED: Final[str] = "routed"
OUTSTANDING: Final[str] = "outstanding"
_NO_OWNING_PLAN: Final[str] = "the attention view attributes it to no plan"


@dataclass(frozen=True, kw_only=True)
class DetectionStalenessRouting:
    """Where the item was routed, and the act by which it gets there."""

    item_id: str
    lifecycle_act: ActionId | None
    plan: str | None
    reason: str
    target: str
    topic: str

    def document(self) -> dict[str, object]:
        return {
            "item_id": self.item_id,
            "lifecycle_act": self.lifecycle_act,
            "plan": self.plan,
            "reason": self.reason,
            "target": self.target,
            "topic": self.topic,
        }


def session_states_by_plan(*, rows: Sequence[Mapping[str, object]]) -> dict[str, str]:
    """The session state this tick read for each plan the roster carries."""
    states: dict[str, str] = {}
    for row in rows:
        plan = row.get("plan")
        state = row.get("session_state")
        if isinstance(plan, str) and plan and isinstance(state, str):
            states[plan] = state
    return states


def _grooming_routing(
    *, item: DetectionStalenessItem, repo_slug: str, why: str
) -> DetectionStalenessRouting:
    topic = grooming_topic(repo_slug=repo_slug)
    return DetectionStalenessRouting(
        item_id=item.item_id,
        lifecycle_act=None,
        plan=item.plan,
        reason=(
            f"routed detection-staleness item '{item.item_id}' ({item.kind}) to the "
            f"grooming operation '{topic}', whose drain pass checks detection "
            f"staleness, because {why}"
        ),
        target=GROOMING_OPERATION,
        topic=topic,
    )


def _attended_routing(
    *, item: DetectionStalenessItem, plan: str, act: ActionId | None
) -> DetectionStalenessRouting:
    reaching = (
        "which is already attended and working"
        if act is None
        else f"which the enumerated act '{act}' starts or resumes"
    )
    return DetectionStalenessRouting(
        item_id=item.item_id,
        lifecycle_act=act,
        plan=plan,
        reason=(
            f"routed detection-staleness item '{item.item_id}' ({item.kind}) to the "
            f"attended session for plan '{plan}', {reaching}"
        ),
        target=ATTENDED_PLAN_SESSION,
        topic=plan,
    )


def route_item(
    *,
    item: DetectionStalenessItem,
    session_states: Mapping[str, str],
    repo_slug: str,
) -> DetectionStalenessRouting:
    """Route one item, failing toward the grooming operation and never toward running."""
    if item.plan is None:
        return _grooming_routing(item=item, repo_slug=repo_slug, why=_NO_OWNING_PLAN)
    state = session_states.get(item.plan)
    if state is None:
        return _grooming_routing(
            item=item, repo_slug=repo_slug, why=f"this roster carries no plan '{item.plan}'"
        )
    if state == SESSION_WORKING:
        return _attended_routing(item=item, plan=item.plan, act=None)
    act = REMEDY_BY_SESSION_STATE.get(state)
    if act is None:
        return _grooming_routing(
            item=item,
            repo_slug=repo_slug,
            why=f"plan '{item.plan}' carries the unreadable session state '{state}'",
        )
    return _attended_routing(item=item, plan=item.plan, act=act)


def detection_staleness_document(
    *, rows: Sequence[Mapping[str, object]], attention: Mapping[str, object] | None, repo: Path
) -> dict[str, object]:
    """The tick's own record of every detection-staleness item and where it was routed."""
    items = detection_staleness_items(attention=attention)
    states = session_states_by_plan(rows=rows)
    routings = [
        route_item(item=item, session_states=states, repo_slug=repo.name)
        for item in (items if items is not None else [])
    ]
    return {
        "available": items is not None,
        "item_count": None if items is None else len(routings),
        "routings": [routing.document() for routing in routings],
        "undetermined_reason": None if items is not None else ATTENTION_VIEW_UNAVAILABLE,
    }


def act_routes_item(*, act: Mapping[str, object], routing: DetectionStalenessRouting) -> bool:
    """True only for the routing act itself, named for this item and an enumerated target."""
    return (
        act.get("kind") == ROUTING_ACT_KIND
        and act.get("item_id") == routing.item_id
        and act.get("target") in ROUTING_TARGETS
    )


def satisfaction(
    *, routing: DetectionStalenessRouting, acts: Sequence[Mapping[str, object]]
) -> str:
    """ROUTED only where the routing was performed; every other act leaves it OUTSTANDING."""
    routed = any(act_routes_item(act=act, routing=routing) for act in acts)
    return ROUTED if routed else OUTSTANDING
