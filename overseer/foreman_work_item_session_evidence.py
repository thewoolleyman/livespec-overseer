"""Ledger-backed evidence checks for foreman work-item sessions."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final

import jsonio
from foreman_gather_sources import parse_repo_config, string_list

__all__: list[str] = ["work_item_session_refusal"]

_ADMITTED_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "active",
        "pending-approval",
        "ready",
    }
)
_CONFIG_PREFIX: Final[re.Pattern[str]] = re.compile(
    r'"livespec-orchestrator-beads-fabro"\s*:\s*\{.*?'
    r'"connection"\s*:\s*\{.*?"prefix"\s*:\s*"([^"]+)"',
    re.DOTALL,
)


def work_item_session_refusal(
    *, repo: Path, document: dict[str, object], work_item_id: str
) -> str | None:
    if attention_has_work_item(document=document, work_item_id=work_item_id):
        return None
    prefix = tenant_prefix(repo=repo)
    if not own_tenant_id(value=work_item_id, prefix=prefix):
        return "foreign_work_item_id"
    item, refusal = read_work_item(repo=repo, work_item_id=work_item_id)
    if refusal is not None:
        return refusal
    status = str_field(payload=item or {}, key="status")
    return None if status in _ADMITTED_STATUSES else "work_item_status_not_admitted"


def attention_has_work_item(*, document: dict[str, object], work_item_id: str) -> bool:
    attention = jsonio.as_object(value=document.get("needs_attention")) or {}
    items = jsonio.as_list(value=attention.get("items")) or []
    objects = [jsonio.as_object(value=item) for item in items]
    return any(item is not None and item.get("id") == work_item_id for item in objects)


def read_work_item(*, repo: Path, work_item_id: str) -> tuple[dict[str, object] | None, str | None]:
    command = [*_credential_wrapper(repo=repo), "bd", "show", work_item_id, "--json"]
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=str(repo),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None, "work_item_evidence_missing"
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return None, "work_item_evidence_missing"
    if completed.returncode != 0:
        return None, "work_item_not_found"
    parsed = jsonio.parse_object(text=completed.stdout)
    if jsonio.is_parse_failure(result=parsed):  # pragma: no cover
        return None, "work_item_evidence_unavailable"
    item = parsed.unwrap()
    if item is None or str_field(payload=item, key="id") != work_item_id:  # pragma: no cover
        return None, "work_item_not_found"
    return item, None


def _credential_wrapper(*, repo: Path) -> list[str]:
    config = parse_repo_config(repo=repo)
    if config is None:
        return []
    wrapper = string_list(value=config.get("credential_wrapper"))
    return wrapper if wrapper is not None else []


def tenant_prefix(*, repo: Path) -> str:
    config = repo / ".livespec.jsonc"
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return "overseer"
    match = _CONFIG_PREFIX.search(text)
    return match.group(1) if match is not None else "overseer"


def own_tenant_id(*, value: str, prefix: str) -> bool:
    return value == prefix or value.startswith(f"{prefix}-")


def str_field(*, payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value != "" else None
