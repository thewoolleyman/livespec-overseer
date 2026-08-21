"""Active-profile identity resolution for caam account rotation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import jsonio

__all__: list[str] = [
    "FAIL_ACTIVE_PROFILE",
    "TOOL",
    "ActiveProfileResolution",
    "CaamProcess",
    "CaamRunner",
    "account_uuid",
    "active_profile",
    "resolve_active_profile",
]

TOOL: Final = "claude"
FAIL_ACTIVE_PROFILE: Final = "FAIL could not determine active claude profile"


class CaamProcess(Protocol):
    returncode: int
    stdout: str


class CaamRunner(Protocol):
    def __call__(self, *, args: tuple[str, ...]) -> CaamProcess: ...


@dataclass(frozen=True, kw_only=True)
class ActiveProfileResolution:
    profile: str | None
    message: str | None
    exit_code: int


def account_uuid(*, claude_json_path: Path) -> str | None:
    """oauthAccount.accountUuid from a .claude.json, or None.

    Stable across token refreshes, which is the whole point of using it.
    """

    try:
        parsed: object = json.loads(claude_json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    body = jsonio.as_object(value=parsed)
    oauth = jsonio.as_object(value=None if body is None else body.get("oauthAccount"))
    uuid = None if oauth is None else oauth.get("accountUuid")
    return uuid if isinstance(uuid, str) else None


def active_profile(
    *,
    live_account_path: Path,
    vault_path: Path,
    caam_runner: CaamRunner,
) -> str | None:
    """Which vault profile is live right now.

    caam's own answer is preferred, but it CANNOT be relied on: caam identifies
    the active profile by byte-matching the live credential against each snapshot,
    and Claude Code refreshes that token roughly every 8 hours as normal operation.
    After any refresh the live file matches nothing and caam omits active_profile
    entirely.

    So fall back to identity: ~/.claude.json carries oauthAccount.accountUuid, which
    does not change when the token rotates. Match that against each snapshot's
    recorded UUID.
    """

    status_profile = _active_profile_from_caam(caam_runner=caam_runner)
    if status_profile is not None:
        return status_profile

    live = account_uuid(claude_json_path=live_account_path)
    if live is None or not vault_path.is_dir():
        return None
    for profile_path in sorted(vault_path.iterdir(), key=lambda path: path.name):
        if profile_path.name.startswith("_"):
            continue
        if account_uuid(claude_json_path=profile_path / ".claude.json") == live:
            return profile_path.name
    return None


def resolve_active_profile(
    *,
    live_account_path: Path,
    vault_path: Path,
    caam_runner: CaamRunner,
) -> ActiveProfileResolution:
    profile = active_profile(
        live_account_path=live_account_path,
        vault_path=vault_path,
        caam_runner=caam_runner,
    )
    if profile is None:
        return ActiveProfileResolution(profile=None, message=FAIL_ACTIVE_PROFILE, exit_code=2)
    return ActiveProfileResolution(profile=profile, message=None, exit_code=0)


def _active_profile_from_caam(*, caam_runner: CaamRunner) -> str | None:
    process = caam_runner(args=("status", "--json"))
    if process.returncode != 0:
        return None
    try:
        parsed: object = json.loads(process.stdout)
    except ValueError:
        return None
    body = jsonio.as_object(value=parsed)
    tools = jsonio.as_list(value=None if body is None else body.get("tools")) or []
    for value in tools:
        entry = jsonio.as_object(value=value)
        if entry is None:
            continue
        active = entry.get("active_profile")
        if entry.get("tool") == TOOL and isinstance(active, str) and active:
            return active
    return None
