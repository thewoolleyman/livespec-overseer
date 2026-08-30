"""Full-autonomy reporting helpers for the foreman runtime."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import jsonio
import ledger_comments
from foreman_runtime_identity import canonical_session_name
from foreman_valve_policy import effective_valve_disposition

__all__: list[str] = [
    "DEFAULT_SEAT_ANCHOR_EPIC",
    "STANDING_ORDERS_TEMPLATE",
    "AttentionCondition",
    "AutonomyReport",
    "SeatComments",
    "attention_conditions",
    "default_seat_comments",
    "full_autonomy_report",
]

DEFAULT_SEAT_ANCHOR_EPIC: Final[str] = "overseer-z5fo4y"
STANDING_ORDERS_MARKER: Final[str] = "STANDING ORDERS"
STANDING_ORDERS_TEMPLATE: Final[str] = (
    "STANDING ORDERS for {repo_name}: full maintainer authority and "
    "decision-making responsibility are delegated to the {foreman_session} "
    "foreman session and process until all active plans are complete and "
    "archived. Workers may disagree with a foreman instruction up to two times; "
    "the third delivery of the same instruction is final and the worker must "
    "take the action. A worker may not stay stalled instead of moving its assigned "
    "plan track forward unless blocked by a hard system, infrastructure, quota, "
    "or credential error that is not resolvable by any other means. Contested "
    "calls go to a cross-vendor consensus panel and MAJORITY OPINION WINS IN "
    "ALL CASES; the only escalation left is a security concern a panel cannot "
    "resolve."
)
ATTENTION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "final-ruling-unheeded",
        "foreman-picker-under-full-autonomy",
    }
)

AttentionCondition = dict[str, str]


@dataclass(frozen=True, kw_only=True)
class AutonomyReport:
    full_autonomy: bool
    decision_rule: object
    conflict: bool
    attention_conditions: list[AttentionCondition]
    standing_orders: str | None
    standing_orders_recorded: bool | None
    full_autonomy_terminating_condition_reached: bool


class SeatComments(Protocol):
    def __call__(self, *, repo: Path, work_item_id: str) -> Sequence[dict[str, object]]: ...


def default_seat_comments(*, repo: Path, work_item_id: str) -> Sequence[dict[str, object]]:
    """The seat anchor's ledger comments; an unreadable ledger reads as none.

    This surface reports only whether the standing orders were recorded, and an
    absent record and an unreadable ledger both mean "not proven recorded" here.
    A caller that must tell those apart reads
    :func:`ledger_comments.read_comments` directly, which keeps them distinct.
    """
    return ledger_comments.read_comments(repo=repo, work_item_id=work_item_id) or ()


def _standing_orders_recorded(*, comments: Sequence[dict[str, object]]) -> bool:
    return any(
        text.startswith(STANDING_ORDERS_MARKER)
        for text in (ledger_comments.comment_text(comment=comment) for comment in comments)
        if text is not None
    )


def _live_plan_count(*, repo: Path) -> int:
    plan = repo / "plan"
    try:
        entries = tuple(plan.iterdir())
    except OSError:
        return 0
    return sum(1 for entry in entries if entry.is_dir() and entry.name != "archive")


def _snapshot_rows(*, document: dict[str, object]) -> Sequence[dict[str, object]]:
    snapshot = jsonio.as_object(value=document.get("snapshot")) or {}
    rows = jsonio.as_list(value=snapshot.get("rows")) or []
    return tuple(row for row in (jsonio.as_object(value=row) for row in rows) if row is not None)


def attention_conditions(*, document: dict[str, object]) -> list[AttentionCondition]:
    items: list[AttentionCondition] = []
    for row in _snapshot_rows(document=document):
        topic = row.get("topic")
        status = row.get("status")
        if isinstance(topic, str) and isinstance(status, str) and status in ATTENTION_STATUSES:
            items.append({"topic": topic, "condition": status})
    return items


def _standing_orders(*, repo: Path) -> str:
    return STANDING_ORDERS_TEMPLATE.format(
        repo_name=repo.name,
        foreman_session=canonical_session_name(repo=repo),
    )


def full_autonomy_report(
    *,
    repo: Path,
    document: dict[str, object],
    seat_anchor_epic: str = DEFAULT_SEAT_ANCHOR_EPIC,
    seat_comments: SeatComments = default_seat_comments,
) -> AutonomyReport:
    disposition = effective_valve_disposition(repo=repo)
    full_autonomy = disposition.get("full_autonomy") is True
    standing_orders = None
    standing_orders_recorded = None
    if full_autonomy:
        standing_orders = _standing_orders(repo=repo)
        standing_orders_recorded = _standing_orders_recorded(
            comments=seat_comments(repo=repo, work_item_id=seat_anchor_epic)
        )
    return AutonomyReport(
        full_autonomy=full_autonomy,
        decision_rule=disposition.get("decision_rule"),
        conflict=disposition.get("conflict") is True,
        attention_conditions=attention_conditions(document=document),
        standing_orders=standing_orders,
        standing_orders_recorded=standing_orders_recorded,
        full_autonomy_terminating_condition_reached=(
            full_autonomy and _live_plan_count(repo=repo) == 0
        ),
    )
