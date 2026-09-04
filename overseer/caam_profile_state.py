"""Profile enumeration, usage cache, and state persistence for caam rotation.

STATE FILE KEY VOCABULARY. Every top-level key the program writes to
``STATE_REL`` is listed here so the next key added does not have to be
inferred from the ones already there:

    foreman_model        caam_foreman_override  -- the persisted foreman pin
    last_switch          caam_switch            -- from/to/at of the last switch
    models               caam_sessions          -- the per-session set memo
    profiles             caam_profile_state     -- the usage snapshot cache
    protected_accounts   caam_protected_accounts-- per-account protection floors
    session_models       caam_session_models    -- per-session model exceptions
    warm                 caam_warm              -- the keep-warm memo

THE CONVENTION IS UNDERSCORES, and it is load-bearing rather than
cosmetic. ``session_models`` shipped hyphenated once (overseer-54k2za.36)
and both maintainer model pins silently stopped applying while still
APPEARING present in the file, because an unrecognised key is loaded and
saved back untouched -- the program preserves it and simply never reads
it. A misspelled key therefore fails silently in the one direction
nobody checks. ``caam_session_models._LEGACY_STATE_KEY`` is the migration
that repair needed; a new key spelled correctly needs no such thing.
"""

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
    "state_path",
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


def state_path(*, home: Path) -> Path:
    return home / STATE_REL


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

    credential_expired = _credential_expired(why=why)
    cached = jsonio.as_object(value=context.seen.get(name))
    if cached is not None and _cache_age(cached=cached, now=context.now) <= cache_max_age_s():
        age = _cache_age(cached=cached, now=context.now)
        return ProfileUsage(
            name=name,
            usage=_usage_from_cache(cached=cached),
            source=f"cached {age / 3600:.1f}h",
            credential_expired=credential_expired,
        )
    return ProfileUsage(
        name=name, usage=None, source=f"dark: {why}", credential_expired=credential_expired
    )


def _credential_expired(*, why: str | None) -> bool:
    """Whether a failed usage read means the STORED CREDENTIAL is expired or absent.

    True only for a credential the revive agent could refresh -- an expired token or
    a snapshot with no token -- never a transient or policy failure (HTTP, network).
    This lets revive act on the maintenance fact the instant it is known, rather than
    an hour later when the cached figures age past the reporting ceiling
    (overseer-54k2za.47).
    """
    return why is not None and (why.startswith("token expired") or why == "no token in snapshot")


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
    """The remembered row, keyed for what it holds.

    The keys carry the direction for the same reason the record's fields do: a
    cache is read by a later pass that has no access to the response it came
    from. The old direction-free keys are deliberately neither written nor read,
    which is what makes a row written before the flip degrade in the SAFE
    direction -- see `_usage_from_cache`.
    """
    return {
        "at": now,
        "five_hour_remaining": usage.five_hour_remaining,
        "seven_day_remaining": usage.seven_day_remaining,
        "five_hour_resets_at": usage.five_hour_resets_at,
        "seven_day_resets_at": usage.seven_day_resets_at,
        "fable_remaining": usage.fable_remaining,
        "fable_resets_at": usage.fable_resets_at,
    }


def _cache_age(*, cached: dict[str, object], now: float) -> float:
    return now - (jsonio.as_float(value=cached.get("at")) or 0.0)


def _usage_from_cache(*, cached: dict[str, object]) -> UsageRecord:
    """A remembered row read back, with an unreadable balance meaning nothing left.

    The missing-key default is zero under both representations, but it means the
    opposite thing under each -- and the remaining direction is the one that
    fails CLOSED. A row written before this flip carries no `*_remaining` key, so
    it reads as an exhausted account and is simply not selected, rather than as a
    fully-available one that the pass would then rotate onto. It self-heals on
    that account's next live poll.
    """
    return UsageRecord(
        five_hour_remaining=jsonio.as_float(value=cached.get("five_hour_remaining")) or 0.0,
        seven_day_remaining=jsonio.as_float(value=cached.get("seven_day_remaining")) or 0.0,
        five_hour_resets_at=_optional_string(value=cached.get("five_hour_resets_at")),
        seven_day_resets_at=_optional_string(value=cached.get("seven_day_resets_at")),
        fable_remaining=jsonio.as_float(value=cached.get("fable_remaining")),
        fable_resets_at=_optional_string(value=cached.get("fable_resets_at")),
    )


def _optional_string(*, value: object) -> str | None:
    return value if isinstance(value, str) else None
