"""The rendered target summary for a completed caam switch."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from caam_decision import ProfileUsage, UsageRecord
from caam_rendering import SwitchTargetSummary

__all__: list[str] = ["target_summary"]


def target_summary(*, target: ProfileUsage, now: float) -> SwitchTargetSummary:
    """Adapt a selected profile into the switch renderer's summary type."""
    usage = cast(UsageRecord, target.usage)
    return SwitchTargetSummary(
        name=target.name,
        weekly_remaining=usage.seven_day_remaining or 0.0,
        weekly_reset=usage.seven_day_resets_at,
        source=target.source,
        now=datetime.fromtimestamp(now, tz=timezone.utc),
    )
