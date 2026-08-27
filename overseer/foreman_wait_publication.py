"""Publication of the foreman's OWN wait states onto the governed plan's ledger epic.

Ratified by v035 in `SPECIFICATION/spec.md`, section "Relay and escalation
discipline": the foreman's own wait states — an open picker it raised, an
escalation awaiting an answer, a panel in progress — MUST be published as state
on the governed plan's LEDGER EPIC, so that what the loop is waiting on is
readable without opening the pane it is waiting in. Publishing them ONLY to the
foreman's private runtime state is not sufficient, and that is exactly what the
three raise sites did before this module existed: the wait lived under
`tmp/overseer/foreman/` and in a pane, which is the state in which a stall goes
unnoticed because nobody can see it without attaching to the pane it is in.

TWO BOUNDARIES ARE LOAD-BEARING HERE, and both are structural rather than
advisory.

The epic is resolved from the LEDGER ALONE, by `ledger_plan_epic_anchor`, which
matches a plan slug against `metadata.plan_slug` on ledger epic records. The
filesystem fallback its `plan_epic_anchor` sibling carries is deliberately NOT
used: that fallback reads `plan/<slug>/epic.md`, and this publication must reach
the plan tree by no route at all. Nothing in this module opens, writes, or stats
a path under `plan/`, so the prohibition stated by section "Non-interference with
tracked work" is unaffected.

Nothing here writes into any orchestrator-owned snapshot either. The needs-
attention snapshot stays unaware of this repository, which is the scope boundary
the ratifying work-item draws.

Publication is FAIL-OPEN, and the ordering at each raise site enforces it: the
private runtime artifact is written FIRST and the publication follows, with a
refusal returned on the failure track rather than raised. An unreachable ledger
therefore degrades the visibility of a wait; it can never stop the foreman from
raising one.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import jsonio
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from foreman_act_dispatch_result import CommandResult, Runner
from foreman_act_ledger import LedgerMutation, ledger_mutation, ledger_request
from foreman_act_types import WORK_ITEM_COMMENT
from foreman_plan_roster_work import ledger_plan_epic_anchor

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ESCALATION_AWAITING_ANSWER",
    "LEDGER_PUBLICATION_FAILED",
    "PANEL_IN_PROGRESS",
    "PICKER_OPEN",
    "PLAN_EPIC_UNRESOLVED",
    "SCHEMA_VERSION",
    "WAIT_HEADLINES",
    "WAIT_KINDS",
    "WAIT_MARKER",
    "PublishedWait",
    "WaitPublication",
    "WaitPublicationRefusal",
    "WaitPublisher",
    "WaitState",
    "default_runner",
    "publish_wait_state",
    "read_wait_states",
    "render_wait_state",
]

SCHEMA_VERSION: Final[int] = 1
WAIT_MARKER: Final[str] = "FOREMAN-WAIT-STATE"

PICKER_OPEN: Final[str] = "picker-open"
ESCALATION_AWAITING_ANSWER: Final[str] = "escalation-awaiting-answer"
PANEL_IN_PROGRESS: Final[str] = "panel-in-progress"
WAIT_KINDS: Final[tuple[str, ...]] = (
    PICKER_OPEN,
    ESCALATION_AWAITING_ANSWER,
    PANEL_IN_PROGRESS,
)
# The headline is what a human reading the epic sees FIRST, so it states the
# wait in the ratified clause's own words rather than in a token.
WAIT_HEADLINES: Final[dict[str, str]] = {
    PICKER_OPEN: "an open picker it raised",
    ESCALATION_AWAITING_ANSWER: "an escalation awaiting an answer",
    PANEL_IN_PROGRESS: "a panel in progress",
}

PLAN_EPIC_UNRESOLVED: Final[str] = "plan_epic_unresolved"
LEDGER_PUBLICATION_FAILED: Final[str] = "ledger_publication_failed"

_TEXT_KEYS: Final[tuple[str, ...]] = ("text", "body", "content")


@dataclass(frozen=True, kw_only=True)
class WaitState:
    """One wait the foreman loop is itself parked on, and the plan that owns it."""

    kind: str
    plan: str
    detail: str


@dataclass(frozen=True, kw_only=True)
class PublishedWait:
    """A wait that reached the ledger, and the epic a reader will find it on."""

    epic_id: str
    text: str


@dataclass(frozen=True, kw_only=True)
class WaitPublicationRefusal:
    """Why a wait did not reach the ledger. Never a reason to withhold the wait."""

    reason: str
    detail: str = ""


WaitPublication = Result[PublishedWait, WaitPublicationRefusal]


class WaitPublisher(Protocol):
    def __call__(self, *, repo: Path, wait: WaitState) -> WaitPublication: ...


def default_runner(*, argv: list[str]) -> CommandResult:  # pragma: no cover
    completed = subprocess.run(  # noqa: S603 — fixed bd argv, no shell
        argv, check=False, capture_output=True, text=True
    )
    return CommandResult(
        returncode=int(completed.returncode),
        stderr=completed.stderr,
        stdout=completed.stdout,
    )


def render_wait_state(*, wait: WaitState) -> str:
    """Render a wait as the ledger comment body a reader consults.

    Two parts, and both are deliberate. The first line is prose a human reads at
    a glance; the second is the machine form :func:`read_wait_states` parses back,
    so the same published state answers an operator and a program without either
    having to open the pane.
    """
    payload: dict[str, object] = {
        "detail": wait.detail,
        "kind": wait.kind,
        "plan": wait.plan,
        "schema_version": SCHEMA_VERSION,
    }
    return (
        f"{WAIT_MARKER}: the foreman loop is waiting on {WAIT_HEADLINES[wait.kind]} "
        f"for plan `{wait.plan}`.\n{json.dumps(payload, sort_keys=True)}"
    )


def read_wait_states(*, comments: Sequence[dict[str, object]]) -> list[WaitState]:
    """Recover every published wait from a plan epic's ledger comments.

    This is the READER half of the ratified clause: given what `bd comments` says
    about the governed plan's epic, it answers what the loop is waiting on. A
    comment that is not a published wait is skipped rather than reported, because
    a plan epic carries ordinary discussion alongside this state.
    """
    recovered: list[WaitState] = []
    for comment in comments:
        wait = _wait_state_from_text(text=_comment_text(comment=comment))
        if wait is not None:
            recovered.append(wait)
    return recovered


def publish_wait_state(
    *,
    repo: Path,
    wait: WaitState,
    epic_records: list[dict[str, object]] | None = None,
    mutate: LedgerMutation = ledger_mutation,
    run: Runner = default_runner,
) -> WaitPublication:
    """Publish one wait onto the governed plan's ledger epic, at the moment it is raised.

    The mutation is routed through the same typed ledger surface every other
    foreman ledger act uses, so the tenant-ownership guard that surface enforces
    applies to this publication too: a wait can only ever be written onto an
    epic in this repository's own tenant.
    """
    resolved = _resolve_epic(repo=repo, plan=wait.plan, epic_records=epic_records)
    if resolved is None:
        return Failure(WaitPublicationRefusal(reason=PLAN_EPIC_UNRESOLVED, detail=wait.plan))
    text = render_wait_state(wait=wait)
    refusal, request = ledger_request(
        proposal={
            "repo": str(repo),
            "work_item_comment": {"work_item_id": resolved, "text": text},
        },
        action_id=WORK_ITEM_COMMENT,
    )
    if request is None:
        return Failure(
            WaitPublicationRefusal(reason=refusal or LEDGER_PUBLICATION_FAILED, detail=resolved)
        )
    try:
        _ = mutate(request=request, run=run)
    except RuntimeError as exc:
        return Failure(WaitPublicationRefusal(reason=LEDGER_PUBLICATION_FAILED, detail=str(exc)))
    return Success(PublishedWait(epic_id=resolved, text=text))


def _resolve_epic(
    *, repo: Path, plan: str, epic_records: list[dict[str, object]] | None
) -> str | None:
    # An empty plan names no governed plan, so it is refused BEFORE any ledger
    # read: a malformed raise must not send a query at a tenant on its behalf.
    if plan == "":
        return None
    return ledger_plan_epic_anchor(repo=repo, plan=plan, records=epic_records)


def _comment_text(*, comment: dict[str, object]) -> str:
    for key in _TEXT_KEYS:
        value = comment.get(key)
        if isinstance(value, str):
            return value
    return ""


def _wait_state_from_text(*, text: str) -> WaitState | None:
    headline, separator, payload_text = text.partition("\n")
    if separator == "" or not headline.startswith(WAIT_MARKER):
        return None
    parsed = jsonio.parse_object(text=payload_text)
    if jsonio.is_parse_failure(result=parsed):
        return None
    payload = parsed.unwrap()
    if payload is None:
        return None
    kind = payload.get("kind")
    plan = payload.get("plan")
    detail = payload.get("detail")
    if kind not in WAIT_KINDS or not isinstance(plan, str) or not isinstance(detail, str):
        return None
    return WaitState(kind=str(kind), plan=plan, detail=detail)
