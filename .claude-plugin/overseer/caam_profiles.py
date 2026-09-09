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
    "ActiveIdentity",
    "ActiveProfileResolution",
    "CaamProcess",
    "CaamRunner",
    "account_uuid",
    "active_profile",
    "resolve_active_profile",
    "unresolved_identity_note",
]

TOOL: Final = "claude"
FAIL_ACTIVE_PROFILE: Final = "FAIL could not determine active claude profile"
_UNRESOLVED_IDENTITY = (
    "note: could not resolve a stable account identifier for the active profile {profile} -- "
    "neither the live account file nor that profile's stored snapshot carries one"
)


class CaamProcess(Protocol):
    returncode: int
    stdout: str
    stderr: str


class CaamRunner(Protocol):
    def __call__(self, *, args: tuple[str, ...]) -> CaamProcess: ...


@dataclass(frozen=True, kw_only=True)
class ActiveIdentity:
    """The account a pass determined active: the profile name AND the account's own id.

    Both are resolved on EVERY path that determines an account, per spec.md --
    "A determined account's stable identifier MUST be resolved whichever path
    determined it", ratified in v049. A profile name
    alone is not a durable name for an account, because renaming a profile would
    silently redirect every consumer keyed on it; and resolving the identifier
    only where the account manager's report is unavailable would make its
    presence depend on which path happened to answer.

    `account_uuid` is None ONLY where no source carries one -- a profile the
    account manager names but has never snapshotted, for instance. That is a
    REPORTED CONDITION rather than a failure path; see `unresolved_identity_note`.
    """

    profile: str
    account_uuid: str | None


@dataclass(frozen=True, kw_only=True)
class ActiveProfileResolution:
    profile: str | None
    account_uuid: str | None
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


def unresolved_identity_note(*, profile: str) -> str:
    """The operator-facing report line for a determined account with no identifier.

    Reported rather than failed: the pass's observation, reporting and rotation
    obligations are unaffected by the gap, per spec.md's "An unresolved identifier
    is a reported condition, not a failure path". It carries the `note:` prefix
    the unverified-candidate note carries, and deliberately not `FAIL`, which
    would tell an operator the pass gave up on work it in fact completed.
    """

    return _UNRESOLVED_IDENTITY.format(profile=profile)


def active_profile(
    *,
    live_account_path: Path,
    vault_path: Path,
    caam_runner: CaamRunner,
) -> ActiveIdentity | None:
    """Which vault profile is live right now, and which ACCOUNT that profile is.

    caam's own answer is preferred, but it CANNOT be relied on: caam identifies
    the active profile by byte-matching the live credential against each snapshot,
    and Claude Code refreshes that token roughly every 8 hours as normal operation.
    After any refresh the live file matches nothing and caam omits active_profile
    entirely.

    So fall back to identity: ~/.claude.json carries oauthAccount.accountUuid, which
    does not change when the token rotates. Match that against each snapshot's
    recorded UUID.

    EITHER path yields the same pair, and that is the point: the identifier is
    resolved whichever path named the profile, so its presence is a property of
    the account rather than an accident of which answer arrived first.
    """

    live = account_uuid(claude_json_path=live_account_path)
    status_profile = _active_profile_from_caam(caam_runner=caam_runner)
    if status_profile is not None:
        return ActiveIdentity(
            profile=status_profile,
            account_uuid=_identifier_of(profile=status_profile, live=live, vault_path=vault_path),
        )

    if live is None or not vault_path.is_dir():
        return None
    for profile_path in sorted(vault_path.iterdir(), key=lambda path: path.name):
        if profile_path.name.startswith("_"):
            continue
        if account_uuid(claude_json_path=profile_path / ".claude.json") == live:
            return ActiveIdentity(profile=profile_path.name, account_uuid=live)
    return None


def _identifier_of(*, profile: str, live: str | None, vault_path: Path) -> str | None:
    """The determined account's stable identifier, from whichever source answers.

    The LIVE account file is read first because it describes the account the host
    is actually spending against, which is what "active" means here. Where it
    carries none -- it can be absent, unreadable, or mid-rewrite -- that profile's
    own stored snapshot answers for the SAME account, since the account manager
    named the profile by byte-matching the live credential against that snapshot.
    """

    if live is not None:
        return live
    return account_uuid(claude_json_path=vault_path / profile / ".claude.json")


def resolve_active_profile(
    *,
    live_account_path: Path,
    vault_path: Path,
    caam_runner: CaamRunner,
) -> ActiveProfileResolution:
    """Determine the active account, or fail loudly having tried both paths.

    An UNRESOLVED IDENTIFIER is not one of those failures: an account determined
    without one still resolves with exit code zero and no message, because the
    condition is reported by the pass rather than treated as a failure path.
    """

    active = active_profile(
        live_account_path=live_account_path,
        vault_path=vault_path,
        caam_runner=caam_runner,
    )
    if active is None:
        return ActiveProfileResolution(
            profile=None,
            account_uuid=None,
            message=FAIL_ACTIVE_PROFILE,
            exit_code=2,
        )
    return ActiveProfileResolution(
        profile=active.profile,
        account_uuid=active.account_uuid,
        message=None,
        exit_code=0,
    )


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
