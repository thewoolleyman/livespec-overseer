"""Validation helpers for typed wait-premise records."""

from __future__ import annotations

from datetime import datetime

__all__: list[str] = [
    "require_kind",
    "require_non_empty",
    "require_timestamp",
    "required_field",
    "timestamp_valid",
]


def require_kind(*, kind: str, kinds: tuple[str, ...]) -> None:
    if kind not in kinds:
        msg = f"kind must be one of {', '.join(kinds)}"
        raise ValueError(msg)


def required_field(*, fields: dict[str, str], field: str) -> str:
    try:
        return fields[field]
    except KeyError:
        msg = f"{field} is required"
        raise ValueError(msg) from None


def require_non_empty(*, field: str, value: str) -> None:
    if value == "":
        msg = f"{field} must be non-empty"
        raise ValueError(msg)


def require_timestamp(*, field: str, value: str) -> None:
    if not timestamp_valid(value=value):
        msg = f"{field} must be an ISO-8601 timestamp"
        raise ValueError(msg)


def timestamp_valid(*, value: str) -> bool:
    try:
        _ = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True
