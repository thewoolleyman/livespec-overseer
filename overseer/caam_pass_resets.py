"""Observe every managed account's quota resets once per rotation pass."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from caam_decision import ProfileUsage
from caam_profile_state import usage_credential_path
from caam_reset_source import ResetSource
from caam_resets import ResetReading

__all__: list[str] = ["observe_pass_resets"]


def observe_pass_resets(
    *,
    active_name: str,
    home: Path,
    now: float,
    profiles: tuple[ProfileUsage, ...],
    source: ResetSource,
) -> tuple[ProfileUsage, ...]:
    """Carry each account's independently-read reset reading into its row."""
    return tuple(
        _with_resets(active_name=active_name, home=home, now=now, profile=profile, source=source)
        for profile in profiles
    )


def _with_resets(
    *,
    active_name: str,
    home: Path,
    now: float,
    profile: ProfileUsage,
    source: ResetSource,
) -> ProfileUsage:
    reading, reason = source(
        creds_path=usage_credential_path(name=profile.name, active_name=active_name, home=home),
        now=now,
    )
    if reading is None:
        reading = ResetReading(resets=(), unreadable_reason=reason or "reset reading failed")
    return replace(profile, reset_reading=reading)
