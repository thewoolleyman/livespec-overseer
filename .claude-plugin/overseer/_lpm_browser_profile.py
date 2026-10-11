"""Owner-only account-specific Chrome profiles and the closed headed launch vector."""

from __future__ import annotations

import os
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
_PRIVATE_BITS = 0o077


def account_profile(
    *, state_dir: Path, provider: str, account_id: str, owner_uid: int
) -> Result[Path, ManagerError]:
    """Atomically create an absent profile below an already-safe profile parent."""
    parent = state_dir / "browser-profiles"
    if not _profile_root_is_safe(profile=parent, owner_uid=owner_uid):
        return _unsafe_profile()
    profile = parent / length_prefixed_digest(values=(provider, account_id))
    try:
        profile.mkdir(mode=_PROFILE_MODE)
    except FileExistsError:
        pass
    except OSError:
        return _unsafe_profile()
    return validate_profile(profile=profile, owner_uid=owner_uid)


def validate_profile(*, profile: Path, owner_uid: int) -> Result[Path, ManagerError]:
    """Validate the complete tree without following, repairing, or replacing any path."""
    if not _profile_tree_is_safe(profile=profile, owner_uid=owner_uid):
        return _unsafe_profile()
    return Success(profile)


def chrome_arguments(*, chrome_executable: str, profile: Path) -> tuple[str, ...]:
    """Return the installed headed-Chrome vector with only private CDP pipes."""
    return (
        chrome_executable,
        f"--user-data-dir={profile}",
        "--remote-debugging-pipe",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--password-store=gnome-libsecret",
        "--disable-features=AutofillServerCommunication,AutofillEnableAccountWalletStorage,PasswordManagerOnboarding",
        "about:blank",
    )


def _profile_root_is_safe(*, profile: Path, owner_uid: int) -> bool:
    try:
        status = profile.lstat()
    except OSError:
        return False
    identity = (stat.S_IFMT(status.st_mode), status.st_uid, stat.S_IMODE(status.st_mode))
    return identity == (stat.S_IFDIR, owner_uid, _PROFILE_MODE)


def _profile_tree_is_safe(*, profile: Path, owner_uid: int) -> bool:
    pending = [profile]
    try:
        while pending:
            path = pending.pop()
            status = path.lstat()
            mode = stat.S_IMODE(status.st_mode)
            is_directory = stat.S_ISDIR(status.st_mode)
            accepted_kind = is_directory or stat.S_ISREG(status.st_mode)
            safe = (
                accepted_kind
                and status.st_uid == owner_uid
                and mode & _PRIVATE_BITS == 0
                and (path != profile or (is_directory and mode == _PROFILE_MODE))
            )
            if not safe:
                return False
            if is_directory:
                with os.scandir(path) as children:
                    pending.extend(Path(child.path) for child in children)
    except OSError:
        return False
    return True


def _unsafe_profile() -> Failure[ManagerError]:
    return Failure(store_unavailable(message="browser profile state is unsafe"))
