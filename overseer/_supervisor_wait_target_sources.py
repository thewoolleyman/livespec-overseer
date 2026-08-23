"""Authoritative-source readers for wait-premise target re-verification."""
# livespec-lloc-soft-band-owner: overseer-tdfe.13

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonio
from _supervisor_records import WaitTargetCacheEntry
from _supervisor_wait_target_forge import forge_pull_request_present_with
from _supervisor_wait_target_liveness import remote_factory_run_present_with
from _supervisor_wait_target_status import (
    WAIT_TARGET_MISSING_STATUS,
)

__all__: list[str] = [
    "cache_key",
    "verify_wait_target_record",
]

_LOCAL_PS_FIXTURE = Path("tmp") / "overseer" / "fabro-ps-a.json"
_JOURNAL = Path("tmp") / "fabro-dispatch-journal.jsonl"
_GIT_TIMEOUT_SECONDS = 5.0
_TERMINAL_STATUSES = frozenset({"failed", "error", "blocked", "canceled", "cancelled"})
_DELIVERED_STATUSES = frozenset({"succeeded", "success", "merged", "closed", "done"})
_REMOTE_FACTORIES = frozenset({"hp", "vps", "remote"})
_LOCAL_FACTORIES = frozenset({"local"})


def string_field(*, record: dict[str, object], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def cache_key(*, record: dict[str, object]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


def remote_record(*, record: dict[str, object]) -> bool:
    location = string_field(record=record, key="execution_location")
    factory = string_field(record=record, key="dispatch_factory")
    source = string_field(record=record, key="evidence_source") or ""
    return (
        location == "remote"
        or (factory or "").lower() in _REMOTE_FACTORIES
        or "factory=hp" in source
        or "factory=vps" in source
    )


def local_record(*, record: dict[str, object]) -> bool:
    location = string_field(record=record, key="execution_location")
    factory = string_field(record=record, key="dispatch_factory")
    source = string_field(record=record, key="evidence_source") or ""
    return (
        location == "local"
        or (factory or "").lower() in _LOCAL_FACTORIES
        or source == "fabro ps -a --json"
    )


def json_records_from_file(*, path: Path) -> list[dict[str, object]] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    items = jsonio.as_list(value=value)
    if items is None:
        return None
    return [item for raw in items if (item := jsonio.as_object(value=raw)) is not None]


def local_process_records(*, repo: Path) -> list[dict[str, object]]:
    fixture = json_records_from_file(path=repo / _LOCAL_PS_FIXTURE)
    if fixture is not None:
        return fixture
    try:
        completed = subprocess.run(  # noqa: S603
            ["fabro", "ps", "-a", "--json"],  # noqa: S607
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    parsed = jsonio.parse_object(text=completed.stdout)
    payload = None if jsonio.is_parse_failure(result=parsed) else parsed.unwrap()
    runs = (
        None
        if payload is None
        else jsonio.as_list(value=payload.get("runs")) or jsonio.as_list(value=payload.get("items"))
    )
    if runs is None:
        return []
    return [item for raw in runs if (item := jsonio.as_object(value=raw)) is not None]


def record_id(*, record: dict[str, object]) -> str | None:
    for key in ("id", "run_id", "dispatch_id"):
        value = string_field(record=record, key=key)
        if value is not None:
            return value
    return None


def record_status(*, record: dict[str, object]) -> str | None:
    for key in ("status", "state", "conclusion"):
        value = string_field(record=record, key=key)
        if value is not None:
            return value.lower()
    return None


def read_journal(*, repo: Path) -> list[dict[str, object]]:
    path = repo / _JOURNAL
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict[str, object]] = []
    for line in lines:
        parsed = jsonio.parse_object_line(line=line)
        if jsonio.is_parse_failure(result=parsed):
            continue
        record = parsed.unwrap()
        if record is not None:
            records.append(record)
    return records


def journal_dispatch_at(
    *, records: list[dict[str, object]], target_id: str, work_item_id: str | None
) -> str:
    latest = ""
    for record in records:
        if record.get("stage") != "dispatch-id":
            continue
        if record.get("dispatch_id") != target_id and record.get("run_id") != target_id:
            continue
        if work_item_id is not None and record.get("work_item_id") != work_item_id:
            continue
        at = string_field(record=record, key="at") or ""
        latest = max(latest, at)
    return latest


def journal_outcomes(
    *, records: list[dict[str, object]], target_id: str, work_item_id: str | None
) -> list[dict[str, object]]:
    floor = journal_dispatch_at(records=records, target_id=target_id, work_item_id=work_item_id)
    outcomes: list[dict[str, object]] = []
    for record in records:
        if record.get("stage") != "outcome":
            continue
        at = string_field(record=record, key="at") or ""
        if floor and at <= floor:
            continue
        outcome = jsonio.as_object(value=record.get("outcome"))
        if outcome is None:
            continue
        outcome_work_item = string_field(record=outcome, key="work_item_id")
        if work_item_id is not None and outcome_work_item != work_item_id:
            continue
        outcome_run = string_field(record=outcome, key="dispatch_id")
        if work_item_id is None and outcome_run != target_id:
            continue
        outcomes.append(outcome)
    return outcomes


def publish_branch_present(*, repo: Path, branch: str | None) -> bool:
    if branch is None:
        return False
    ref = branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), "ls-remote", "--heads", "origin", ref],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


def forge_pull_request_present(*, repo: Path, branch: str | None) -> bool:
    return forge_pull_request_present_with(repo=repo, branch=branch, run=subprocess.run)


def remote_factory_run_present(
    *, repo: Path, record: dict[str, object], target_id: str
) -> bool | None:
    return remote_factory_run_present_with(
        repo=repo,
        record=record,
        target_id=target_id,
        run=subprocess.run,
    )


def local_verdict(*, repo: Path, target_id: str) -> tuple[str, str | None]:
    for record in local_process_records(repo=repo):
        if record_id(record=record) != target_id:
            continue
        status = record_status(record=record)
        if status in _TERMINAL_STATUSES:
            return (
                WAIT_TARGET_MISSING_STATUS,
                f"fabro-run {target_id} present with terminal state {status}",
            )
        return "present", None
    return WAIT_TARGET_MISSING_STATUS, f"fabro-run {target_id} absent from every mandatory leg"


def remote_outcomes_verdict(
    *, outcomes: list[dict[str, object]], target_id: str
) -> tuple[str, str | None] | None:
    if not outcomes:
        return None
    status = record_status(record=outcomes[-1])
    if status in _TERMINAL_STATUSES:
        return (
            WAIT_TARGET_MISSING_STATUS,
            f"fabro-run {target_id} present with terminal state {status}",
        )
    if status in _DELIVERED_STATUSES or status is not None:
        return "present", None
    return WAIT_TARGET_MISSING_STATUS, f"fabro-run {target_id} absent from every mandatory leg"


def remote_verdict(
    *, repo: Path, record: dict[str, object], target_id: str
) -> tuple[str, str | None]:
    branch = string_field(record=record, key="publish_branch")
    if publish_branch_present(repo=repo, branch=branch):
        return "present", None
    work_item_id = string_field(record=record, key="work_item_id")
    outcomes = journal_outcomes(
        records=read_journal(repo=repo), target_id=target_id, work_item_id=work_item_id
    )
    outcomes_verdict = remote_outcomes_verdict(outcomes=outcomes, target_id=target_id)
    if outcomes_verdict is not None:
        return outcomes_verdict
    if forge_pull_request_present(repo=repo, branch=branch):
        return "present", None
    remote_liveness = remote_factory_run_present(repo=repo, record=record, target_id=target_id)
    if remote_liveness is True or (
        remote_liveness is None and string_field(record=record, key="dispatch_factory") is not None
    ):
        return "present", None
    return WAIT_TARGET_MISSING_STATUS, f"fabro-run {target_id} absent from every mandatory leg"


def verify_wait_target_record(
    *, repo: Path, record: dict[str, object], cache: WaitTargetCacheEntry | None, now: float
) -> WaitTargetCacheEntry:
    if cache is not None and cache.checked_at == now:
        return cache
    target_id = string_field(record=record, key="target_id")
    if target_id is None or record.get("kind") != "fabro-run":
        return WaitTargetCacheEntry(checked_at=now, status="present", note=None)
    if local_record(record=record) and not remote_record(record=record):
        status, note = local_verdict(repo=repo, target_id=target_id)
    else:
        status, note = remote_verdict(repo=repo, record=record, target_id=target_id)
    return WaitTargetCacheEntry(checked_at=now, status=status, note=note)
