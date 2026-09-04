"""Switch target summary adapter for caam account rotation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from caam_decision_models import ProfileUsage, UsageRecord
from caam_rendering import SwitchTargetSummary

__all__: list[str] = [
    "target_summary",
]


def target_summary(*, target: ProfileUsage, now: float) -> SwitchTargetSummary:
    usage = cast(UsageRecord, target.usage)
    return SwitchTargetSummary(
        name=target.name,
        weekly_remaining=usage.seven_day_remaining,
        weekly_reset=usage.seven_day_resets_at,
        source=target.source,
        now=datetime.fromtimestamp(now, tz=timezone.utc),
    )
