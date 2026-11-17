"""Presentation-only summaries for CAAM account-table cells."""

from __future__ import annotations

from datetime import datetime
from math import inf

from caam_resets import ResetReading

__all__: list[str] = ["quota_resets_cell", "unrecognised_limits_cell"]


def quota_resets_cell(*, reading: ResetReading | None, now: datetime) -> str:
    """Summarize one account's reset uses without exposing reset-record detail."""
    if reading is None or reading.unreadable_reason is not None:
        return "unreadable"
    uses_left = tuple(max(0, reset.uses_left) for reset in reading.resets)
    total = sum(uses_left)
    if not total:
        return "0"
    from caam_decision import resets_at

    next_lapse = min(
        (
            lapse
            for reset, uses in zip(reading.resets, uses_left, strict=True)
            if uses and (lapse := resets_at(timestamp=reset.lapses_at)) != inf
        ),
        default=inf,
    )
    if next_lapse == inf:
        return str(total)
    seconds = max(0, int(next_lapse - now.timestamp()))
    days, seconds = divmod(seconds, 86_400)
    return f"{total}, next expires in {days}d {seconds // 3_600}h"


def unrecognised_limits_cell(
    *, limits: tuple[tuple[str, float, str | None], ...], now: datetime
) -> str:
    """Render unrecognised provider limits without changing the primary table contract."""
    from caam_rendering import until

    return (
        ", ".join(
            f"{kind} {remaining:.0f}%"
            + (f" (reset {until(timestamp=reset_at, now=now)})" if reset_at is not None else "")
            for kind, remaining, reset_at in limits
        )
        or "-"
    )
