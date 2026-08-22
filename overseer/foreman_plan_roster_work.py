"""Dispatch-journal work state for foreman plan roster rows."""

from __future__ import annotations

import re
from pathlib import Path

import jsonio

__all__: list[str] = [
    "NO_WORK_IN_FLIGHT",
    "WORK_IN_FLIGHT",
    "WORK_STATES",
    "work_states_by_plan",
]

WORK_IN_FLIGHT = "work-in-flight"
NO_WORK_IN_FLIGHT = "no-work-in-flight"
WORK_STATES = (WORK_IN_FLIGHT, NO_WORK_IN_FLIGHT)
DEFAULT_JOURNAL_RELATIVE_PATH = Path("tmp") / "fabro-dispatch-journal.jsonl"
_LEDGER_ANCHOR = re.compile(
    r"(?:[Ll]edger(?: epic)?|[Ee]pic) anchor:?\*{0,2}[^\n`]*\n?[^\n`]*`([a-z0-9-]+(?:\.[0-9]+)?)`"
)
_LEDGER_ANCHOR_BARE = re.compile(
    r"^#\s*(?:[Ll]edger(?: epic)?|[Ee]pic) anchor\s*$\n+^([a-z0-9-]+(?:\.[0-9]+)?)\s*$",
    re.MULTILINE,
)


def plan_epic_anchor(*, repo: Path, plan: str) -> str | None:
    path = repo / "plan" / plan / "epic.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    match = _LEDGER_ANCHOR.search(text)
    if match is not None:
        return match.group(1)
    bare_match = _LEDGER_ANCHOR_BARE.search(text)
    if bare_match is not None:
        return bare_match.group(1)
    return None


def journal_records(*, path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed_result = jsonio.parse_object_line(line=line)
        if jsonio.is_parse_failure(result=parsed_result):
            continue
        parsed = parsed_result.unwrap()
        if parsed is not None:
            records.append(parsed)
    return records


def record_time(*, record: dict[str, object]) -> str:
    at = record.get("at")
    return at if isinstance(at, str) else ""


def record_work_item_id(*, record: dict[str, object]) -> str | None:
    if record.get("stage") == "dispatch-id":
        work_item_id = record.get("work_item_id")
        return work_item_id if isinstance(work_item_id, str) else None
    if record.get("stage") == "outcome":
        outcome = jsonio.as_object(value=record.get("outcome"))
        if outcome is not None:
            work_item_id = outcome.get("work_item_id")
            return work_item_id if isinstance(work_item_id, str) else None
    return None


def latest_dispatch_times(*, records: list[dict[str, object]]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for record in records:
        if record.get("stage") != "dispatch-id":
            continue
        work_item_id = record_work_item_id(record=record)
        at = record_time(record=record)
        if work_item_id is not None and at >= latest.get(work_item_id, ""):
            latest[work_item_id] = at
    return latest


def outcome_times(*, records: list[dict[str, object]]) -> dict[str, list[str]]:
    outcomes: dict[str, list[str]] = {}
    for record in records:
        if record.get("stage") != "outcome":
            continue
        work_item_id = record_work_item_id(record=record)
        if work_item_id is not None:
            outcomes.setdefault(work_item_id, []).append(record_time(record=record))
    return outcomes


def child_in_flight(
    *, child_id: str, dispatch_times: dict[str, str], outcomes: dict[str, list[str]]
) -> bool:
    dispatch_at = dispatch_times.get(child_id)
    if dispatch_at is None:
        return False
    return not any(outcome_at > dispatch_at for outcome_at in outcomes.get(child_id, []))


def plan_work_state(
    *,
    anchor: str | None,
    dispatch_times: dict[str, str],
    outcomes: dict[str, list[str]],
) -> str:
    if anchor is None:
        return NO_WORK_IN_FLIGHT
    child_ids = [child_id for child_id in dispatch_times if child_id.startswith(f"{anchor}.")]
    if any(
        child_in_flight(child_id=child_id, dispatch_times=dispatch_times, outcomes=outcomes)
        for child_id in child_ids
    ):
        return WORK_IN_FLIGHT
    return NO_WORK_IN_FLIGHT


def work_states_by_plan(
    *, repo: Path, plan_names: list[str], journal_path: Path | None = None
) -> dict[str, str]:
    path = journal_path if journal_path is not None else repo / DEFAULT_JOURNAL_RELATIVE_PATH
    records = journal_records(path=path)
    dispatch_times = latest_dispatch_times(records=records)
    outcomes = outcome_times(records=records)
    return {
        plan: plan_work_state(
            anchor=plan_epic_anchor(repo=repo, plan=plan),
            dispatch_times=dispatch_times,
            outcomes=outcomes,
        )
        for plan in plan_names
    }
