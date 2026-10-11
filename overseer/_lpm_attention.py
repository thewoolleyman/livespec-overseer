"""Read the exact secret-free operator view of pending attention artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_at_or_after, is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AttentionItem",
    "attention_item_object",
    "attention_items",
]


@dataclass(frozen=True, kw_only=True)
class AttentionItem:
    """The six members an operator may learn from one pending artifact."""

    path: str
    record_id: str
    provider: str
    account_id: str
    reason: str
    deadline: str


def attention_item_object(*, item: AttentionItem) -> dict[str, object]:
    """Encode one attention item with exactly the public member set."""
    return {
        "path": item.path,
        "record_id": item.record_id,
        "provider": item.provider,
        "account_id": item.account_id,
        "reason": item.reason,
        "deadline": item.deadline,
    }


def attention_items(
    *, state_dir: Path, owner_uid: int
) -> Result[tuple[AttentionItem, ...], ManagerError]:
    """Read pending artifacts in absolute-path byte order."""
    directory = state_dir / "attention"
    if not directory.is_dir():
        return Success(())
    items: list[AttentionItem] = []
    for path in sorted(directory.glob("*.json"), key=lambda candidate: str(candidate).encode()):
        stored = read_local_record(path=path, owner_uid=owner_uid).unwrap()
        decoded = _attention_item(path=path, parsed=stored)
        if isinstance(decoded, Failure):
            return decoded
        item = decoded.unwrap()
        if item is not None:
            items.append(item)
    return Success(tuple(items))


def _attention_item(*, path: Path, parsed: object) -> Result[AttentionItem | None, ManagerError]:
    source = cast("dict[str, object]", parsed)
    defect = _artifact_defect(source=source)
    if defect is not None:
        return _malformed(message=defect)
    if source["status"] != "pending":
        return Success(None)
    return Success(
        AttentionItem(
            path=str(path.absolute()),
            record_id=cast("str", source["record_id"]),
            provider=cast("str", source["provider"]),
            account_id=cast("str", source["account_id"]),
            reason=cast("str", source["reason"]),
            deadline=cast("str", source["deadline"]),
        )
    )


def _artifact_defect(*, source: dict[str, object]) -> str | None:
    for inspect in (
        _artifact_header_defect,
        _artifact_identity_defect,
        _artifact_worker_defect,
        _artifact_binding_defect,
        _artifact_time_defect,
    ):
        defect = inspect(source=source)
        if defect is not None:
            return defect
    return None


def _artifact_header_defect(*, source: dict[str, object]) -> str | None:
    version = source["version"]
    if isinstance(version, bool) or version != 1:
        return "attention version must be the integer 1"
    if source["type"] != "browser-verification-wall":
        return "attention type is invalid"
    if source["reason"] not in ("captcha", "two-factor"):
        return "attention reason is invalid"
    if source["status"] not in ("pending", "resolved", "give-up"):
        return "attention status is invalid"
    return None


def _artifact_identity_defect(*, source: dict[str, object]) -> str | None:
    for member in ("record_id", "operation_id"):
        value = source[member]
        if not isinstance(value, str) or not is_uuid4(value=value):
            return f"attention {member} must be a lowercase UUIDv4"
    return None


def _artifact_worker_defect(*, source: dict[str, object]) -> str | None:
    worker_pid = source["worker_pid"]
    if isinstance(worker_pid, bool) or not isinstance(worker_pid, int) or worker_pid <= 0:
        return "attention worker_pid must be a positive integer"
    ticks = source["worker_start_ticks"]
    if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
        return "attention worker_start_ticks must be a non-negative integer"
    return None


def _artifact_binding_defect(*, source: dict[str, object]) -> str | None:
    for member in ("provider", "account_id"):
        value = source[member]
        if not isinstance(value, str) or value == "":
            return f"attention {member} must be a non-empty string"
    return None


def _artifact_time_defect(*, source: dict[str, object]) -> str | None:
    for member in ("raised_at", "deadline"):
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return f"attention {member} must be a UTC RFC 3339-second timestamp"
    if (
        is_at_or_after(
            moment=cast("str", source["raised_at"]),
            limit=cast("str", source["deadline"]),
        )
        is not False
    ):
        return "attention deadline must be later than raised_at"
    return None


def _malformed(*, message: str) -> Failure[ManagerError]:
    return Failure(store_unavailable(message=message))
