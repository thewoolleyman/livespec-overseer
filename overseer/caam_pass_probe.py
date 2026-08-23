"""Live-probe profiles that the vault holds no usage snapshot for.

Split out of `caam_anthropic_pass` when carrier R12's trigger header pushed that
module past the 250-LLOC hard ceiling (overseer-54k2za.38). This pair is the
natural seam: it is self-contained, it is the only place that re-probes a
snapshotless profile, and it needs nothing from the pass orchestration beyond
the home directory and the pass timestamp.

It deliberately takes those two primitives rather than a `PassContext`, so the
dependency runs one way only and `caam_anthropic_pass` can import it without a
cycle.
"""

from __future__ import annotations

from pathlib import Path

from caam_anthropic_decide import UsageFetcher
from caam_decision import ProfileUsage
from caam_profile_state import caam_vault

__all__: list[str] = [
    "probe_snapshotless_profiles",
]

_NO_SNAPSHOT = "dark: no snapshot"


def probe_snapshotless_profiles(
    *,
    home: Path,
    now: float,
    profiles: tuple[ProfileUsage, ...],
    fetcher: UsageFetcher,
) -> tuple[ProfileUsage, ...]:
    return tuple(
        _probe_snapshotless_profile(home=home, now=now, profile=profile, fetcher=fetcher)
        for profile in profiles
    )


def _probe_snapshotless_profile(
    *,
    home: Path,
    now: float,
    profile: ProfileUsage,
    fetcher: UsageFetcher,
) -> ProfileUsage:
    if profile.usage is not None or profile.source != _NO_SNAPSHOT:
        return profile
    usage, _ = fetcher(
        creds_path=caam_vault(home=home) / profile.name / ".credentials.json",
        now=now,
    )
    if usage is None:
        return profile
    return ProfileUsage(name=profile.name, source="live", usage=usage)
