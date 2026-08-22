# livespec-lloc-soft-band-owner: overseer-2jblyq.8
"""Dispatch-journal work state for foreman plan roster rows."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import cast

import jsonio
from foreman_gather_sources import parse_repo_config, string_list
from foreman_plan_roster_work_items import plan_dispatch_item_ids, work_item_plan_anchors

__all__: list[str] = [
    "ANCHOR_RESOLVED",
    "ANCHOR_UNRESOLVED",
    "NO_WORK_IN_FLIGHT",
    "WORK_IN_FLIGHT",
    "WORK_STATES",
    "work_state_documents_by_plan",
    "work_states_by_plan",
]

ANCHOR_RESOLVED = "anchor-resolved"
ANCHOR_UNRESOLVED = "anchor-unresolved"
WORK_IN_FLIGHT = "work-in-flight"
NO_WORK_IN_FLIGHT = "no-work-in-flight"
WORK_STATES = (WORK_IN_FLIGHT, NO_WORK_IN_FLIGHT)
DEFAULT_JOURNAL_RELATIVE_PATH = Path("tmp") / "fabro-dispatch-journal.jsonl"
LEDGER_EPIC_COMMAND = [
    "bd",
    "list",
    "--type",
    "epic",
    "--status",
    "all",
    "--limit",
    "0",
    "--json",
]
LEDGER_WORK_ITEM_COMMAND = ["bd", "list", "--status", "all", "--limit", "0", "--json"]
LEDGER_TIMEOUT_SECONDS = 30
_LEDGER_ANCHOR = re.compile(
    r"(?:[Ll]edger(?: epic)?|[Ee]pic) anchor:?\*{0,2}[^\n`]*\n?[^\n`]*`([a-z0-9-]+(?:\.[0-9]+)?)`"
)
_LEDGER_ANCHOR_BARE = re.compile(
    r"^#\s*(?:[Ll]edger(?: epic)?|[Ee]pic) anchor\s*$\n+^([a-z0-9-]+(?:\.[0-9]+)?)\s*$",
    re.MULTILINE,
)


def _credential_wrapper(*, repo: Path) -> list[str]:
    config = parse_repo_config(repo=repo)
    if config is None:
        return []
    wrapper = string_list(value=config.get("credential_wrapper"))
    return wrapper if wrapper is not None else []


def _ledger_records(*, repo: Path, ledger_command: list[str]) -> list[dict[str, object]]:
    command = [*_credential_wrapper(repo=repo), *ledger_command]
    try:
        completed = subprocess.run(  # noqa: S603 — fixed bd argv, no shell
            command,
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=LEDGER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    records: list[dict[str, object]] = []
    for raw_item in cast("list[object]", parsed):
        item = jsonio.as_object(value=raw_item)
        if item is not None:
            records.append(item)
    return records


def ledger_epic_records(*, repo: Path) -> list[dict[str, object]]:
    return _ledger_records(repo=repo, ledger_command=LEDGER_EPIC_COMMAND)


def ledger_work_item_records(*, repo: Path) -> list[dict[str, object]]:
    return _ledger_records(repo=repo, ledger_command=LEDGER_WORK_ITEM_COMMAND)


def ledger_plan_epic_anchor(
    *, repo: Path, plan: str, records: list[dict[str, object]] | None = None
) -> str | None:
    matches: list[tuple[str, object]] = []
    epic_records = records if records is not None else ledger_epic_records(repo=repo)
    for item in epic_records:
        if item.get("issue_type") != "epic":
            continue
        record_id = item.get("id")
        metadata = jsonio.as_object(value=item.get("metadata"))
        if (
            isinstance(record_id, str)
            and metadata is not None
            and metadata.get("plan_slug") == plan
        ):
            matches.append((record_id, item.get("status")))
    if len(matches) == 1:
        return matches[0][0]
    open_matches = [record_id for record_id, status in matches if status != "closed"]
    if len(open_matches) == 1:
        return open_matches[0]
    return None


def plan_epic_anchor(
    *, repo: Path, plan: str, ledger_records: list[dict[str, object]] | None = None
) -> str | None:
    ledger_anchor = ledger_plan_epic_anchor(repo=repo, plan=plan, records=ledger_records)
    if ledger_anchor is not None:
        return ledger_anchor
    # Keep epic.md as a legacy fallback: current plans carry plan_slug in Beads,
    # but older plan directories may still be filesystem-anchored.
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


def plan_anchor_resolved(*, repo: Path, plan: str) -> bool:
    return plan_epic_anchor(repo=repo, plan=plan) is not None


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
    plan_anchors_by_item_id: dict[str, str],
) -> str:
    if anchor is None:
        return NO_WORK_IN_FLIGHT
    child_ids = plan_dispatch_item_ids(
        anchor=anchor,
        dispatch_item_ids=list(dispatch_times),
        plan_anchors_by_item_id=plan_anchors_by_item_id,
    )
    if any(
        child_in_flight(child_id=child_id, dispatch_times=dispatch_times, outcomes=outcomes)
        for child_id in child_ids
    ):
        return WORK_IN_FLIGHT
    return NO_WORK_IN_FLIGHT


def work_states_by_plan(
    *, repo: Path, plan_names: list[str], journal_path: Path | None = None
) -> dict[str, str]:
    return {
        plan: document["work_state"]
        for plan, document in work_state_documents_by_plan(
            repo=repo,
            plan_names=plan_names,
            journal_path=journal_path,
        ).items()
    }


def work_state_documents_by_plan(
    *, repo: Path, plan_names: list[str], journal_path: Path | None = None
) -> dict[str, dict[str, str]]:
    path = journal_path if journal_path is not None else repo / DEFAULT_JOURNAL_RELATIVE_PATH
    records = journal_records(path=path)
    dispatch_times = latest_dispatch_times(records=records)
    outcomes = outcome_times(records=records)
    epic_records = ledger_epic_records(repo=repo)
    work_item_records = ledger_work_item_records(repo=repo)
    plan_anchors_by_item_id = work_item_plan_anchors(records=work_item_records)
    documents: dict[str, dict[str, str]] = {}
    for plan in plan_names:
        anchor = plan_epic_anchor(repo=repo, plan=plan, ledger_records=epic_records)
        documents[plan] = {
            "work_state": plan_work_state(
                anchor=anchor,
                dispatch_times=dispatch_times,
                outcomes=outcomes,
                plan_anchors_by_item_id=plan_anchors_by_item_id,
            ),
            "work_state_evidence": ANCHOR_RESOLVED if anchor is not None else ANCHOR_UNRESOLVED,
        }
    return documents
