"""The per-account observations a pass layers onto its polled rows.

Moved out of `caam_anthropic_pass`, which sits against its LLOC ceiling. Both are
read-only requests made with each account's own credential, and both are settled
before the table renders, so they travel together.
"""

from __future__ import annotations

from pathlib import Path

from caam_decision import ProfileUsage
from caam_pass_capacity import observe_pass_capacity
from caam_pass_resets import observe_pass_resets
from caam_pass_seams import PassSeams

__all__: list[str] = ["observe_pass_rows"]


def observe_pass_rows(
    *,
    active_name: str,
    home: Path,
    now: float,
    profiles: tuple[ProfileUsage, ...],
    seams: PassSeams,
) -> tuple[ProfileUsage, ...]:
    """Capacity class first, then the reset instants, over the same rows."""
    profiles = observe_pass_capacity(
        active_name=active_name,
        home=home,
        now=now,
        profiles=profiles,
        source=seams.capacity_source,
    )
    return observe_pass_resets(
        active_name=active_name,
        home=home,
        now=now,
        profiles=profiles,
        source=seams.reset_source,
    )
