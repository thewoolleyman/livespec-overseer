"""Read the exact secret-free operator view of pending attention artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Result, Success

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
        source = cast("dict[str, object]", stored)
        if source["status"] == "pending":
            items.append(
                AttentionItem(
                    path=str(path),
                    record_id=cast("str", source["record_id"]),
                    provider=cast("str", source["provider"]),
                    account_id=cast("str", source["account_id"]),
                    reason=cast("str", source["reason"]),
                    deadline=cast("str", source["deadline"]),
                )
            )
    return Success(tuple(items))
