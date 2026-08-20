"""Typed ledger mutations for the deterministic foreman actuator."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final, Protocol

import jsonio
from foreman_act_types import (
    FOREMAN_EPIC_CREATE,
    WORK_ITEM_COMMENT,
    WORK_ITEM_UPDATE,
    ActionId,
)

__all__: list[str] = [
    "LedgerMutation",
    "ledger_mutation",
    "ledger_request",
]

LedgerMutationResult = tuple[str, str]


class LedgerMutation(Protocol):
    def __call__(self, *, request: dict[str, object]) -> LedgerMutationResult: ...


_CONFIG_PREFIX: Final[re.Pattern[str]] = re.compile(
    r'"livespec-orchestrator-beads-fabro"\s*:\s*\{.*?'
    r'"connection"\s*:\s*\{.*?"prefix"\s*:\s*"([^"]+)"',
    re.DOTALL,
)
_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "acceptance",
        "approval",
        "capacity",
        "human_valve",
        "move",
        "policy",
        "rejection",
        "status",
        "valve",
    }
)


def ledger_request(
    *, proposal: dict[str, object], action_id: ActionId
) -> tuple[str | None, dict[str, object] | None]:
    repo = _str_field(payload=proposal, key="repo")
    if repo is None:  # pragma: no cover
        return "malformed_ledger_mutation", None
    prefix = _tenant_prefix(repo=Path(repo))
    if prefix is None:  # pragma: no cover
        return "missing_tenant_prefix", None
    if action_id == WORK_ITEM_UPDATE:
        return _update_request(proposal=proposal, repo=repo, prefix=prefix)
    if action_id == WORK_ITEM_COMMENT:
        return _comment_request(proposal=proposal, repo=repo, prefix=prefix)
    if action_id == FOREMAN_EPIC_CREATE:
        return _epic_create_request(proposal=proposal, repo=repo)
    return "malformed_ledger_mutation", None  # pragma: no cover


def ledger_mutation(*, request: dict[str, object]) -> LedgerMutationResult:  # pragma: no cover
    argv = _command_for(request=request)
    completed = subprocess.run(  # noqa: S603
        argv, cwd=str(request["repo"]), check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        msg = completed.stderr.strip() or f"ledger subprocess exited {completed.returncode}"
        raise RuntimeError(msg)
    return _subprocess_result(action_id=str(request["action_id"]), stdout=completed.stdout)


def _command_for(*, request: dict[str, object]) -> list[str]:  # pragma: no cover
    action_id = str(request["action_id"])
    if action_id == WORK_ITEM_UPDATE:
        return _update_command(request=request)
    if action_id == WORK_ITEM_COMMENT:
        return [
            "bd",
            "comment",
            str(request["work_item_id"]),
            str(request["text"]),
        ]
    return [
        "bd",
        "create",
        str(request["title"]),
        "--type",
        "epic",
        "--description",
        str(request["description"]),
        "--json",
    ]


def _update_command(*, request: dict[str, object]) -> list[str]:  # pragma: no cover
    command = ["bd", "update", str(request["work_item_id"])]
    priority = request.get("priority")
    parent = request.get("parent")
    if isinstance(priority, str):
        command.extend(["--priority", priority])
    if isinstance(parent, str):
        command.extend(["--parent", parent])
    return command


def _subprocess_result(*, action_id: str, stdout: str) -> LedgerMutationResult:  # pragma: no cover
    if action_id == FOREMAN_EPIC_CREATE:
        parsed = jsonio.parse_object(text=stdout)
        item_id = _str_field(payload=parsed or {}, key="id") or _str_field(
            payload=parsed or {}, key="item_id"
        )
        return item_id or "unknown", "created"
    if action_id == WORK_ITEM_COMMENT:
        return "comment", "commented"
    return "update", "updated"


def _update_request(
    *, proposal: dict[str, object], repo: str, prefix: str
) -> tuple[str | None, dict[str, object] | None]:
    payload = _payload(proposal=proposal, key="work_item_update")
    if payload is None:  # pragma: no cover
        return "malformed_ledger_mutation", None
    if _has_forbidden_key(payload=payload):
        return "unsupported_ledger_mutation", None
    item_id = _str_field(payload=payload, key="work_item_id")
    priority = _str_field(payload=payload, key="priority")
    parent = _optional_id(payload=payload, key="parent")
    if item_id is None or (priority is None and parent is None):  # pragma: no cover
        return "malformed_ledger_mutation", None
    if not _own_tenant_id(value=item_id, prefix=prefix) or (
        parent is not None and not _own_tenant_id(value=parent, prefix=prefix)  # pragma: no cover
    ):
        return "foreign_work_item_id", None
    request: dict[str, object] = {
        "action_id": WORK_ITEM_UPDATE,
        "repo": repo,
        "work_item_id": item_id,
    }
    if priority is not None:  # pragma: no branch
        request["priority"] = priority
    if parent is not None:  # pragma: no branch
        request["parent"] = parent
    return None, request


def _comment_request(
    *, proposal: dict[str, object], repo: str, prefix: str
) -> tuple[str | None, dict[str, object] | None]:
    payload = _payload(proposal=proposal, key="work_item_comment")
    if payload is None:  # pragma: no cover
        return "malformed_ledger_mutation", None
    if _has_forbidden_key(payload=payload):
        return "unsupported_ledger_mutation", None
    item_id = _str_field(payload=payload, key="work_item_id")
    text = _str_field(payload=payload, key="text")
    if item_id is None or text is None:  # pragma: no cover
        return "malformed_ledger_mutation", None
    if not _own_tenant_id(value=item_id, prefix=prefix):  # pragma: no cover
        return "foreign_work_item_id", None
    request: dict[str, object] = {
        "action_id": WORK_ITEM_COMMENT,
        "repo": repo,
        "work_item_id": item_id,
        "text": text,
    }
    return None, request


def _epic_create_request(
    *, proposal: dict[str, object], repo: str
) -> tuple[str | None, dict[str, object] | None]:
    payload = _payload(proposal=proposal, key="foreman_epic_create")
    if payload is None:  # pragma: no cover
        return "malformed_ledger_mutation", None
    if _has_forbidden_key(payload=payload):  # pragma: no cover
        return "unsupported_ledger_mutation", None
    if _str_field(payload=payload, key="existing_epic_id") is not None:  # pragma: no cover
        return "foreman_epic_exists", None
    target_repo = _str_field(payload=payload, key="target_repo")
    title = _str_field(payload=payload, key="title")
    description = _str_field(payload=payload, key="description")
    if target_repo != repo or title is None or description is None:  # pragma: no cover
        return "malformed_ledger_mutation", None
    return None, {
        "action_id": FOREMAN_EPIC_CREATE,
        "repo": repo,
        "target_repo": target_repo,
        "title": title,
        "description": description,
    }


def _payload(*, proposal: dict[str, object], key: str) -> dict[str, object] | None:
    return jsonio.as_object(value=proposal.get(key))


def _str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None


def _optional_id(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None


def _has_forbidden_key(*, payload: dict[str, object]) -> bool:
    return any(key in payload for key in _FORBIDDEN_KEYS)


def _own_tenant_id(*, value: str, prefix: str) -> bool:
    return value == prefix or value.startswith(f"{prefix}-")


def _tenant_prefix(*, repo: Path) -> str | None:
    config = repo / ".livespec.jsonc"
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return "overseer"
    match = _CONFIG_PREFIX.search(text)  # pragma: no cover
    return match.group(1) if match is not None else None  # pragma: no cover
