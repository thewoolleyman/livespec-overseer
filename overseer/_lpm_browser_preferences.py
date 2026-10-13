"""Deterministic owner-only Chrome preferences established before browser launch."""

from __future__ import annotations

from pathlib import Path

from _lpm_localstate import ensure_state_directory, write_local_record
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Failure, Result

__all__: list[str] = [
    "prepare_browser_preferences",
]

_PREFERENCES: dict[str, object] = {
    "autofill": {
        "credit_card_enabled": False,
        "profile_enabled": False,
    },
    "credentials_enable_service": False,
    "profile": {
        "password_manager_enabled": False,
    },
}


def prepare_browser_preferences(*, profile: Path, owner_uid: int) -> Result[None, ManagerError]:
    """Create the private Default tree and atomically disable secret-bearing helpers."""
    default = profile / "Default"
    prepared = ensure_state_directory(path=default, owner_uid=owner_uid)
    if isinstance(prepared, Failure):
        return prepared
    return write_local_record(
        path=default / "Preferences",
        value=_PREFERENCES,
        owner_uid=owner_uid,
    )
