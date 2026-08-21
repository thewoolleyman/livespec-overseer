"""Profile enumeration, usage cache, and state persistence for caam rotation."""

from __future__ import annotations

import json
import os as _os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import jsonio
from caam_decision import ProfileUsage, UsageRecord
from caam_usage import fetch_usage

__all__: list[str] = [
    "STATE_REL",
    "caam_vault",
    "cache_max_age_s",
    "live_creds_path",
    "load_state",
    "poll_profiles",
    "profile_names",
    "save_state",
]

_TOOL: Final = "claude"
_VAULT_REL: Final = Path(".local/share/caam/vault") / _TOOL
_LIVE_CREDS_REL: Final = Path(".claude/.credentials.json")
STATE_REL: Final = Path(".local/state/caam-usage-rotate/state.json")
_CACHE_DEFAULT_S: Final = "3600"


class _OsSeam:
    @staticmethod
    def replace(*, src: Path, dst: Path) -> None:
        _ = src.replace(dst)


os = _OsSeam()


class UsageFetcher(Protocol):
    def __call__(
        self,
        *,
        creds_path: Path,
        now: float | None = None,
    ) -> tuple[UsageRecord | None, str | None]: ...


def caam_vault(*, home: Path) -> Path:
    return home / _VAULT_REL


def live_creds_path(*, home: Path) -> Path:
    return home / _LIVE_CREDS_REL


def cache_max_age_s() -> float:
    return float(_os.environ.get("CAAM_ROTATE_CACHE_MAX_AGE_S", _CACHE_DEFAULT_S))


def profile_names(*, vault: Path, active_name: str | None) -> tuple[str, ...]:
    if vault.is_dir():
        names = tuple(
            sorted(path.name for path in vault.iterdir() if not path.name.startswith("_"))
        )
    else:
        names = ()
    if active_name and active_name not in names:
        return (*names, active_name)
    return names


def load_state(*, state_path: Path) -> dict[str, object]:
    try:
        parsed = jsonio.parse_object(text=state_path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    if jsonio.is_parse_failure(result=parsed):
        return {}
    body = parsed.unwrap()
    return {} if body is None else body


def save_state(*, state: dict[str, object], state_path: Path) -> None:
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path = state_path.with_name(state_path.name + ".tmp")
    _ = tmp_path.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    tmp_path.chmod(0o600)
    os.replace(src=tmp_path, dst=state_path)


def poll_profiles(
    *,
    active_name: str | None,
    state: dict[str, object],
    home: Path,
    now: float | None = None,
    fetcher: UsageFetcher = fetch_usage,
) -> tuple[ProfileUsage, ...]:
    checked_at = time.time() if now is None else now
    seen = _cached_profiles(state=state)
    context = _PollContext(
        active_name=active_name,
        seen=seen,
        home=home,
        vault=caam_vault(home=home),
        now=checked_at,
        fetcher=fetcher,
    )
    return tuple(
        _poll_profile(name=name, context=context)
        for name in profile_names(vault=context.vault, active_name=active_name)
    )


def _cached_profiles(*, state: dict[str, object]) -> dict[str, object]:
    cached = jsonio.as_object(value=state.get("profiles"))
    if cached is None:
        cached = {}
        state["profiles"] = cached
    return cached


@dataclass(frozen=True, kw_only=True)
class _PollContext:
    active_name: str | None
    seen: dict[str, object]
    home: Path
    vault: Path
    now: float
    fetcher: UsageFetcher


def _poll_profile(*, name: str, context: _PollContext) -> ProfileUsage:
    usage, why = _fetch_profile_usage(
        name=name,
        active_name=context.active_name,
        home=context.home,
        vault=context.vault,
        now=context.now,
        fetcher=context.fetcher,
    )
    if usage is not None:
        context.seen[name] = _cache_record(usage=usage, now=context.now)
        return ProfileUsage(name=name, usage=usage, source="live")

    cached = jsonio.as_object(value=context.seen.get(name))
    if cached is not None and _cache_age(cached=cached, now=context.now) <= cache_max_age_s():
        age = _cache_age(cached=cached, now=context.now)
        return ProfileUsage(
            name=name,
            usage=_usage_from_cache(cached=cached),
            source=f"cached {age / 3600:.1f}h",
        )
    return ProfileUsage(name=name, usage=None, source=f"dark: {why}")


def _fetch_profile_usage(
    *,
    name: str,
    active_name: str | None,
    home: Path,
    vault: Path,
    now: float,
    fetcher: UsageFetcher,
) -> tuple[UsageRecord | None, str | None]:
    if name == active_name:
        return fetcher(creds_path=live_creds_path(home=home), now=now)

    snapshot = vault / name / ".credentials.json"
    if not snapshot.exists():
        return None, "no snapshot"
    return fetcher(creds_path=snapshot, now=now)


def _cache_record(*, usage: UsageRecord, now: float) -> dict[str, object]:
    return {
        "at": now,
        "five_hour": usage.five_hour,
        "seven_day": usage.seven_day,
        "five_hour_resets_at": usage.five_hour_resets_at,
        "seven_day_resets_at": usage.seven_day_resets_at,
        "fable": usage.fable,
        "fable_resets_at": usage.fable_resets_at,
    }


def _cache_age(*, cached: dict[str, object], now: float) -> float:
    return now - (jsonio.as_float(value=cached.get("at")) or 0.0)


def _usage_from_cache(*, cached: dict[str, object]) -> UsageRecord:
    return UsageRecord(
        five_hour=jsonio.as_float(value=cached.get("five_hour")) or 0.0,
        seven_day=jsonio.as_float(value=cached.get("seven_day")) or 0.0,
        five_hour_resets_at=_optional_string(value=cached.get("five_hour_resets_at")),
        seven_day_resets_at=_optional_string(value=cached.get("seven_day_resets_at")),
        fable=jsonio.as_float(value=cached.get("fable")),
        fable_resets_at=_optional_string(value=cached.get("fable_resets_at")),
    )


def _optional_string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None
