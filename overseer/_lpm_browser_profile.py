"""Owner-only account-specific Chrome profiles and the closed headed launch vector."""

from __future__ import annotations

import stat
from pathlib import Path

from _lpm_canonical import length_prefixed_digest
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "account_profile",
    "chrome_arguments",
    "validate_profile",
]

_PROFILE_MODE = 0o700


def account_profile(
    *, state_dir: Path, provider: str, account_id: str, owner_uid: int
) -> Result[Path, ManagerError]:
    """Create an absent account profile beneath an already-safe profile parent."""
    parent = state_dir / "browser-profiles"
    return validate_profile(profile=parent, owner_uid=owner_uid).map(
        lambda _validated: _create_account_profile(
            parent=parent,
            provider=provider,
            account_id=account_id,
            owner_uid=owner_uid,
        ).unwrap()
    )


def validate_profile(*, profile: Path, owner_uid: int) -> Result[Path, ManagerError]:
    """Accept only a real owner-only directory, never a followed symlink."""
    status = profile.lstat()
    safe = (
        not profile.is_symlink()
        and stat.S_ISDIR(status.st_mode)
        and status.st_uid == owner_uid
        and stat.S_IMODE(status.st_mode) == _PROFILE_MODE
    )
    return {
        False: Failure(store_unavailable(message="browser profile state is unsafe")),
        True: Success(profile),
    }[safe]


def chrome_arguments(*, chrome_executable: str, profile: Path) -> tuple[str, ...]:
    """Return the installed headed-Chrome vector with only private CDP pipes."""
    return (
        chrome_executable,
        f"--user-data-dir={profile}",
        "--remote-debugging-pipe",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-features=AutofillServerCommunication,AutofillEnableAccountWalletStorage,PasswordManagerOnboarding",
        "about:blank",
    )


def _create_account_profile(
    *, parent: Path, provider: str, account_id: str, owner_uid: int
) -> Result[Path, ManagerError]:
    profile = parent / length_prefixed_digest(values=(provider, account_id))
    profile.mkdir(mode=_PROFILE_MODE, exist_ok=True)
    return validate_profile(profile=profile, owner_uid=owner_uid)
