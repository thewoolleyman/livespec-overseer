"""Identity-only factory selection propagation for enrolled-host delivery."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from caam_delivery_push_state import Host
from caam_factory_selection import FACTORY_SELECTION_RECORD_REL

__all__: list[str] = ["factory_record", "factory_targets", "record_factory_result"]


def factory_record(*, home: Path) -> tuple[bytes, str] | None:
    """Return the holder's complete identity-only record with a valid write time."""
    try:
        value = (home / FACTORY_SELECTION_RECORD_REL).read_bytes()
        decoded = json.loads(value)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    body = cast(dict[str, object], decoded) if isinstance(decoded, dict) else {}
    written_at = body.get("written_at")
    if not _valid(body=body, written_at=written_at):
        return None
    return value, cast(str, written_at)


def factory_targets(
    *,
    hosts: list[Host],
    behind: list[Host],
    state: dict[str, dict[str, object]],
    factory_record: tuple[bytes, str] | None,
) -> list[Host]:
    """Add every host that has not recorded the current factory selection."""
    if factory_record is None:
        return behind
    written_at = factory_record[1]
    return [
        host
        for host in hosts
        if host in behind or state.get(host.label, {}).get("factory_written_at") != written_at
    ]


def record_factory_result(
    *, entry: dict[str, object], line: str, factory_record: tuple[bytes, str] | None
) -> None:
    """Remember propagation only after the remote program accepted the record."""
    words = line.split()
    accepted = words[:1] in (
        ["applied"],
        ["stale-sequence"],
        ["not-converted"],
        ["factory-applied"],
    ) or (words[:1] == ["failed"] and len(words) > 1 and words[1].isdigit())
    if factory_record is not None and accepted:
        entry["factory_written_at"] = factory_record[1]


def _valid(*, body: dict[str, object], written_at: object) -> bool:  # noqa: PLR0911
    profile, account, reason = body.get("profile"), body.get("account_uuid"), body.get("reason")
    if set(body) != {"profile", "account_uuid", "written_at", "reason"}:
        return False
    if (profile is None) != (account is None):
        return False
    if profile is not None and (not isinstance(profile, str) or not isinstance(account, str)):
        return False
    if (profile is None and (not isinstance(reason, str) or not reason)) or (
        profile is not None and reason is not None
    ):
        return False
    if not isinstance(written_at, str):
        return False
    try:
        return datetime.fromisoformat(written_at.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False
