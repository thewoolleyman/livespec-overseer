"""Observe every polled account's capacity class, once per pass.

Split out of `caam_anthropic_pass` for the same reason `caam_pass_probe` was:
this is self-contained, it is the only place a plan is read for a row, and it
needs nothing from the pass orchestration beyond the home directory, the active
account's name and the pass timestamp. It takes those primitives rather than a
`PassContext`, so the dependency runs one way only.

THE READ IS MADE PER ACCOUNT, WITH THAT ACCOUNT'S OWN CREDENTIAL, which is why
the credential is resolved through `caam_profile_state.usage_credential_path` --
the same function the usage poll resolves its own credential with. The
specification requires the capacity read to be made with "the same credential
the pass uses for that account's usage", and sharing the derivation is what
makes that structural rather than a coincidence two call sites maintain.

A FAILED READ IS NOT A FAILED PASS. Every reason the source hands back becomes
`unknown`, with no stored or guessed fallback and no effect on the exit code: an
account whose plan could not be read is still an account whose quota the pass
reports and whose rotation it decides.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from caam_capacity import CapacitySource, capacity_of
from caam_decision import ProfileUsage
from caam_profile_state import usage_credential_path

__all__: list[str] = [
    "observe_pass_capacity",
]


def observe_pass_capacity(
    *,
    active_name: str,
    home: Path,
    now: float,
    profiles: tuple[ProfileUsage, ...],
    source: CapacitySource,
) -> tuple[ProfileUsage, ...]:
    """Each row again, carrying the capacity class this pass observed for it."""

    return tuple(
        _with_capacity(active_name=active_name, home=home, now=now, profile=profile, source=source)
        for profile in profiles
    )


def _with_capacity(
    *,
    active_name: str,
    home: Path,
    now: float,
    profile: ProfileUsage,
    source: CapacitySource,
) -> ProfileUsage:
    tier, _ = source(
        creds_path=usage_credential_path(name=profile.name, active_name=active_name, home=home),
        now=now,
    )
    return replace(profile, capacity=capacity_of(tier=tier))
