"""Cache and budget accounting for the report-only consensus panel."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

import jsonio
from foreman_consensus_types import CACHE_TTL_SECONDS, PANEL_SCHEMA_VERSION

__all__: list[str] = [
    "budget_result",
    "read_cached_verdict",
    "record_panel_result",
]

DATE_FORMAT: Final[str] = "%Y-%m-%d"


def now_epoch() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def today() -> str:
    return datetime.now(tz=timezone.utc).strftime(DATE_FORMAT)


def int_field(*, payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def cache_path(*, state_dir: Path, key: str) -> Path:
    return state_dir / "consensus" / f"{key}.json"


def daily_path(*, state_dir: Path) -> Path:
    return state_dir / "budget" / f"{today()}.json"


def write_json(*, path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        _ = handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def daily_count(*, state_dir: Path) -> int:
    path = daily_path(state_dir=state_dir)
    if not path.is_file():
        return 0
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    if jsonio.is_parse_failure(result=parsed):
        return 0
    payload = parsed.unwrap()
    return 0 if payload is None else int_field(payload=payload, key="panels")


def read_cached_verdict(*, state_dir: Path, key: str) -> dict[str, object] | None:
    path = cache_path(state_dir=state_dir, key=key)
    if not path.is_file():
        return None
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    if jsonio.is_parse_failure(result=parsed):
        return None
    cached = parsed.unwrap()
    if cached is None:
        return None
    written_at = int_field(payload=cached, key="written_at_epoch")
    ttl = int_field(payload=cached, key="ttl_seconds")
    verdict = jsonio.as_object(value=cached.get("verdict"))
    if written_at <= 0 or ttl <= 0 or now_epoch() - written_at > ttl or verdict is None:
        return None
    return verdict


def budget_result(*, reason: str, cache_key: str) -> dict[str, object]:
    return {
        "schema_version": PANEL_SCHEMA_VERSION,
        "outcome": "budget_exceeded",
        "reason": reason,
        "cache_key": cache_key,
        "mutated": False,
    }


def record_panel_result(
    *,
    state_dir: Path,
    daily_panel_budget: int | None = None,
    cache_key: str = "",
    verdict: dict[str, object] | None = None,
) -> bool:
    state_dir.mkdir(parents=True, exist_ok=True)
    if daily_panel_budget is not None:
        count = daily_count(state_dir=state_dir)
        if count >= daily_panel_budget:
            return False
        write_json(
            path=daily_path(state_dir=state_dir), payload={"date": today(), "panels": count + 1}
        )
        return True
    if verdict is not None:
        write_json(
            path=cache_path(state_dir=state_dir, key=cache_key),
            payload={
                "written_at_epoch": now_epoch(),
                "ttl_seconds": CACHE_TTL_SECONDS,
                "verdict": verdict,
            },
        )
    return True
