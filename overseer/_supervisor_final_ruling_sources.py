"""Authoritative sources for final-ruling attention."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import jsonio

__all__: list[str] = [
    "FinalRelay",
    "branch_moved",
    "exemption_label",
    "ledger_comment_moved",
    "read_journal",
    "relay_from_record",
    "timestamp",
]

_GIT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True, kw_only=True)
class FinalRelay:
    at: float
    item_id: str
    session_identity: str | None
    branch: str | None
    branch_head: str | None
    latest_plan_comment_at: float | None


@dataclass(frozen=True, kw_only=True)
class LedgerItem:
    blocked_reason: str | None
    latest_comment_at: float | None


def relay_from_record(
    *, record: dict[str, object], fallback_item_id: str | None
) -> FinalRelay | None:
    if record.get("final") is not True:
        return None
    at = timestamp(value=record.get("at"))
    item_id = string_value(value=record.get("work_item_id")) or fallback_item_id
    if at is None or item_id is None:
        return None
    return FinalRelay(
        at=at,
        item_id=item_id,
        session_identity=string_value(value=record.get("session_identity")),
        branch=string_value(value=record.get("branch")),
        branch_head=string_value(value=record.get("branch_head")),
        latest_plan_comment_at=timestamp(value=record.get("latest_plan_comment_at")),
    )


def exemption_label(*, repo: Path, item_id: str) -> str | None:
    item = read_ledger_item(repo=repo, item_id=item_id)
    if item is not None and item.blocked_reason == "infra-external":
        return "infra-external"
    if credential_exhaustion_refusal(repo=repo, item_id=item_id):
        return "credential-exhaustion"
    if caam_quota_exhausted(repo=repo):
        return "caam-quota-exhausted"
    if factory_host_failure(repo=repo, item_id=item_id):
        return "factory-host-failure"
    return None


def branch_moved(*, repo: Path, relay: FinalRelay) -> bool:
    if relay.branch is None or relay.branch_head is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), "rev-parse", relay.branch],  # noqa: S607
            capture_output=True,
            check=False,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and completed.stdout.strip() != relay.branch_head


def ledger_comment_moved(*, repo: Path, relay: FinalRelay) -> bool:
    item = read_ledger_item(repo=repo, item_id=relay.item_id)
    if item is None or item.latest_comment_at is None:
        return False
    floor = relay.latest_plan_comment_at if relay.latest_plan_comment_at is not None else relay.at
    return item.latest_comment_at > floor


def credential_exhaustion_refusal(*, repo: Path, item_id: str) -> bool:
    records = read_journal(repo=repo) or ()
    matches = tuple(
        record
        for record in records
        if string_value(value=record.get("work_item_id")) == item_id
        and string_value(value=record.get("outcome")) in {"refused", "failed"}
    )
    if not matches:
        return False
    reason = string_value(value=matches[-1].get("reason")) or ""
    return "429" in reason and "exhaust" in reason.lower()


def caam_quota_exhausted(*, repo: Path) -> bool:
    payload = read_json_object(path=repo / "tmp" / "overseer" / "caam-quota.json")
    if payload is None:
        return False
    return (
        payload.get("account_window_exhausted") is True or payload.get("window_exhausted") is True
    )


def factory_host_failure(*, repo: Path, item_id: str) -> bool:
    root = repo / "tmp" / "overseer" / "detached-dispatch"
    try:
        logs = tuple(root.glob(f"{item_id}-*/output.log"))
    except OSError:
        return False
    for log in logs:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "fabro-run" in text and ("ENOSPC" in text or "No space left on device" in text):
            return True
    return False


def read_journal(*, repo: Path) -> tuple[dict[str, object], ...] | None:
    path = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    records: list[dict[str, object]] = []
    for line in lines:
        parsed = jsonio.parse_object_line(line=line)
        if not jsonio.is_parse_failure(result=parsed):
            record = parsed.unwrap()
            if record is not None:
                records.append(record)
    return tuple(records)


def read_ledger_item(*, repo: Path, item_id: str) -> LedgerItem | None:
    payload = read_json_object(path=repo / "tmp" / "overseer" / "ledger-items" / f"{item_id}.json")
    if payload is None:
        return None
    metadata = jsonio.as_object(value=payload.get("metadata")) or {}
    comments = jsonio.as_list(value=payload.get("comments")) or []
    timestamps = tuple(
        parsed
        for comment in (jsonio.as_object(value=value) for value in comments)
        if comment is not None
        and (parsed := timestamp(value=comment.get("created_at") or comment.get("at"))) is not None
    )
    return LedgerItem(
        blocked_reason=string_value(value=metadata.get("blocked_reason")),
        latest_comment_at=max(timestamps) if timestamps else None,
    )


def read_json_object(*, path: Path) -> dict[str, object] | None:
    try:
        parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    except OSError:
        return None
    if jsonio.is_parse_failure(result=parsed):
        return None
    return parsed.unwrap()


def timestamp(*, value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def string_value(*, value: object) -> str | None:
    return value if isinstance(value, str) and value else None
