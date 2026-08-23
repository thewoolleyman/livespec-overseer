"""Factory process-view source reader for remote wait-target verification."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import jsonio
from _supervisor_wait_target_journal import journal_run_ids, read_journal

__all__: list[str] = [
    "remote_factory_run_present_with",
]

_FABRO_REMOTE_TIMEOUT_SECONDS = 12.0
_TERMINAL_STATUSES = frozenset(
    {
        "blocked",
        "canceled",
        "cancelled",
        "closed",
        "done",
        "error",
        "failed",
        "merged",
        "success",
        "succeeded",
    }
)


def string_field(*, record: dict[str, object], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def strip_jsonc_line_comment(*, line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = in_string
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string and char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            return line[:index]
    return line


def parse_repo_config(*, repo: Path) -> dict[str, object] | None:
    try:
        text = (repo / ".livespec.jsonc").read_text(encoding="utf-8")
    except OSError:
        return None
    stripped = "\n".join(strip_jsonc_line_comment(line=line) for line in text.splitlines())
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return jsonio.as_object(value=value)


def dispatcher_config(*, repo: Path) -> dict[str, object] | None:
    config = parse_repo_config(repo=repo)
    if config is None:
        return None
    dispatcher_owner_config = jsonio.as_object(
        value=config.get("livespec-orchestrator-beads-fabro")
    )
    if dispatcher_owner_config is None:
        return None
    return jsonio.as_object(value=dispatcher_owner_config.get("dispatcher"))


def factory_server(*, repo: Path, factory: str | None) -> str | None:
    if factory is None:
        return None
    dispatcher = dispatcher_config(repo=repo)
    if dispatcher is None:
        return None
    factories = jsonio.as_object(value=dispatcher.get("factories"))
    if factories is None:
        return None
    factory_config = jsonio.as_object(value=factories.get(factory))
    if factory_config is None:
        return None
    return string_field(record=factory_config, key="server")


def process_records_from_payload(*, stdout: str) -> list[dict[str, object]] | None:
    try:
        parsed: object = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    runs = jsonio.as_list(value=parsed)
    if runs is None:
        payload = jsonio.as_object(value=parsed)
        if payload is None:
            return None
        runs = jsonio.as_list(value=payload.get("runs"))
        if runs is None:
            runs = jsonio.as_list(value=payload.get("items"))
    if runs is None:
        return None
    return [item for raw in runs if (item := jsonio.as_object(value=raw)) is not None]


def goal_mentions_work_item(*, process_record: dict[str, object], work_item_id: str | None) -> bool:
    goal = string_field(record=process_record, key="goal")
    return work_item_id is not None and goal is not None and work_item_id in goal


def run_matches_target(
    *,
    process_record: dict[str, object],
    target_id: str,
    work_item_id: str | None,
    target_run_ids: frozenset[str] | None = None,
) -> bool:
    run_id = string_field(record=process_record, key="run_id")
    if target_run_ids is not None and run_id in target_run_ids:
        return True
    ids = (
        string_field(record=process_record, key="id"),
        run_id,
        string_field(record=process_record, key="dispatch_id"),
    )
    if target_id in ids:
        return True
    if (
        work_item_id is not None
        and string_field(record=process_record, key="work_item_id") == work_item_id
    ):
        return True
    # Wait premises are keyed on dispatch id; remote factory rows are keyed on
    # run_id. Prefer the dispatch journal's structured bridge above. The goal
    # text fallback exists only when no matching dispatch journal row exists.
    return target_run_ids is None and goal_mentions_work_item(
        process_record=process_record, work_item_id=work_item_id
    )


def status_token(*, process_record: dict[str, object], key: str) -> str | None:
    status = string_field(record=process_record, key=key)
    if status is not None:
        return status
    status_object = jsonio.as_object(value=process_record.get(key))
    if status_object is None:
        return None
    return string_field(record=status_object, key="kind")


def active_process(*, process_record: dict[str, object]) -> bool:
    for key in ("status", "state", "conclusion"):
        status = status_token(process_record=process_record, key=key)
        if status is not None:
            return status.lower() not in _TERMINAL_STATUSES
    return True


def remote_factory_run_present_with(
    *,
    repo: Path,
    record: dict[str, object],
    target_id: str,
    run: Callable[..., CompletedProcess[str]],
) -> bool | None:
    """Return remote liveness, or ``None`` when the factory cannot answer."""
    dispatch_factory = string_field(record=record, key="dispatch_factory")
    if dispatch_factory is None:
        return False
    server = factory_server(repo=repo, factory=dispatch_factory)
    if server is None:
        return None
    try:
        completed = run(
            ["fabro", "ps", "-a", "--json", "--server", server],
            capture_output=True,
            check=False,
            cwd=repo,
            text=True,
            timeout=_FABRO_REMOTE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    records = process_records_from_payload(stdout=completed.stdout)
    if records is None:
        return None
    work_item_id = string_field(record=record, key="work_item_id")
    target_run_ids = journal_run_ids(
        records=read_journal(repo=repo), target_id=target_id, work_item_id=work_item_id
    )
    return any(
        active_process(process_record=process_record)
        for process_record in records
        if run_matches_target(
            process_record=process_record,
            target_id=target_id,
            work_item_id=work_item_id,
            target_run_ids=target_run_ids,
        )
    )
