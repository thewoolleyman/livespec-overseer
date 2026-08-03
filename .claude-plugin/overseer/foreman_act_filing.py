"""Typed work-item filing for the deterministic foreman actuator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Protocol

import jsonio

__all__: list[str] = [
    "FileWorkItem",
    "FiledWorkItem",
    "file_work_item",
    "filing_request",
]

FiledWorkItem = tuple[str, str]


class FileWorkItem(Protocol):
    def __call__(self, *, request: dict[str, object]) -> FiledWorkItem: ...


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None


def _optional_str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if value is None or isinstance(value, str) else ""


def _bool_field(*, payload: dict[str, object], key: str) -> bool | None:
    value = payload.get(key)
    return value if isinstance(value, bool) else None


def _depends_on(*, value: object) -> list[object] | None:
    items = jsonio.as_list(value=value)
    if items is None:  # pragma: no cover
        return None
    return list(items)


def _checklist(*, value: object) -> dict[str, bool] | None:
    raw = jsonio.as_object(value=value)
    if raw is None:  # pragma: no cover
        return None
    keys = (
        "single_coherent_done",
        "autonomously_verifiable",
        "autonomy_tiered",
        "dependency_linked",
        "repo_targeted",
        "above_floor",
    )
    checked: dict[str, bool] = {}
    for key in keys:
        item = _bool_field(payload=raw, key=key)
        if item is None:
            return None
        checked[key] = item
    return checked


def filing_request(*, proposal: dict[str, object]) -> dict[str, object] | None:
    raw = jsonio.as_object(value=proposal.get("filing"))
    if raw is None:  # pragma: no cover
        return None
    target_repo = _str_field(payload=raw, key="target_repo")
    title = _str_field(payload=raw, key="title")
    description = _str_field(payload=raw, key="description")
    work_type = _str_field(payload=raw, key="type")
    assignee = _optional_str_field(payload=raw, key="assignee")
    acceptance = _optional_str_field(payload=raw, key="acceptance_criteria")
    notes = _optional_str_field(payload=raw, key="notes")
    hint = _optional_str_field(payload=raw, key="spec_commitment_hint")
    depends_on = _depends_on(value=raw.get("depends_on"))
    checklist = _checklist(value=raw.get("checklist"))
    if (
        target_repo is None
        or not Path(target_repo).is_absolute()
        or title is None
        or description is None
        or work_type is None
        or assignee == ""
        or acceptance == ""
        or notes == ""
        or hint == ""
        or depends_on is None
        or checklist is None
    ):
        return None
    return {
        "target_repo": target_repo,
        "title": title,
        "description": description,
        "type": work_type,
        "assignee": assignee,
        "depends_on": depends_on,
        "acceptance_criteria": acceptance,
        "notes": notes,
        "spec_commitment_hint": hint,
        "checklist": checklist,
    }


def file_work_item(*, request: dict[str, object]) -> FiledWorkItem:  # pragma: no cover
    """File a freeform item, then route it through the shared six-gate intake seam."""
    target_repo = str(request["target_repo"])
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _FILING_SCRIPT],
        input=json.dumps(request, sort_keys=True),
        text=True,
        capture_output=True,
        check=False,
        cwd=target_repo,
    )
    if completed.returncode != 0:  # pragma: no cover
        msg = completed.stderr.strip() or f"filing subprocess exited {completed.returncode}"
        raise RuntimeError(msg)
    parsed = jsonio.parse_object(text=completed.stdout)
    if parsed is None:  # pragma: no cover
        msg = "filing subprocess returned malformed JSON"
        raise ValueError(msg)
    item_id = _str_field(payload=parsed, key="item_id")
    verdict = _str_field(payload=parsed, key="verdict")
    if item_id is None or verdict is None:  # pragma: no cover
        msg = "filing subprocess returned malformed fields"
        raise ValueError(msg)
    return item_id, verdict


_FILING_SCRIPT = """
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from livespec_orchestrator_beads_fabro._ids import new_work_item_id
from livespec_orchestrator_beads_fabro.commands._config import resolve_store_config
from livespec_orchestrator_beads_fabro.intake_dor import (
    DefinitionOfReadyChecklist,
    apply_intake_dor,
)
from livespec_orchestrator_beads_fabro.store import append_work_item
from livespec_orchestrator_beads_fabro.types import WorkItem
from livespec_runtime.work_items.rank import key_between

request = json.load(sys.stdin)
target_repo = Path(request["target_repo"])
config = resolve_store_config(cwd=target_repo, work_items_arg=None)
item = WorkItem(
    id=new_work_item_id(prefix=config.prefix),
    type=request["type"],
    status="backlog",
    title=request["title"],
    description=request["description"],
    origin="freeform",
    gap_id=None,
    rank=key_between(a=None, b=None),
    assignee=request["assignee"],
    depends_on=tuple(request["depends_on"]),
    captured_at=datetime.now(tz=timezone.utc).isoformat(),
    resolution=None,
    reason=None,
    audit=None,
    superseded_by=None,
    spec_commitment_hint=request["spec_commitment_hint"],
    acceptance_criteria=request["acceptance_criteria"],
    notes=request["notes"],
)
append_work_item(path=config, item=item)
checklist = request["checklist"]
verdict = apply_intake_dor(
    path=config,
    item_id=item.id,
    checklist=DefinitionOfReadyChecklist(
        single_coherent_done=checklist["single_coherent_done"],
        autonomously_verifiable=checklist["autonomously_verifiable"],
        autonomy_tiered=checklist["autonomy_tiered"],
        dependency_linked=checklist["dependency_linked"],
        repo_targeted=checklist["repo_targeted"],
        above_floor=checklist["above_floor"],
    ),
)
print(json.dumps({"item_id": item.id, "verdict": verdict}, sort_keys=True))
"""
