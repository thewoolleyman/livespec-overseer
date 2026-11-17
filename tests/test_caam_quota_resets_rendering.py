"""Acceptance coverage for the account table's quota-reset summary."""

from __future__ import annotations

from datetime import datetime

from caam_decision_models import ProfileUsage, UsageRecord
from caam_rendering import render_table
from caam_resets import QuotaReset, ResetReading

__all__: list[str] = []


def test_table_summarizes_reset_uses_and_the_soonest_expiry() -> None:
    """Two one-use resets render their combined uses and earliest lapse."""
    now = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    resets = ResetReading(
        resets=(
            QuotaReset(
                program="five-day",
                reset_id="first",
                clears=("five_hour",),
                uses_left=1,
                uses_total=1,
                lapses_at="2026-01-06T04:59:00Z",
                usable_now=True,
                requires_limit=False,
            ),
            QuotaReset(
                program="eight-day",
                reset_id="second",
                clears=("seven_day",),
                uses_left=1,
                uses_total=1,
                lapses_at="2026-01-09T00:00:00Z",
                usable_now=True,
                requires_limit=False,
            ),
        )
    )
    row = ProfileUsage(
        name="anthropic-0",
        source="live",
        usage=UsageRecord(
            five_hour_remaining=80.0,
            seven_day_remaining=70.0,
            five_hour_resets_at="2026-01-01T05:00:00Z",
            seven_day_resets_at="2026-01-08T00:00:00Z",
            fable_remaining=None,
            fable_resets_at=None,
        ),
        reset_reading=resets,
    )

    table = render_table(rows=(row,), active_name="anthropic-0", now=now)
    header, rendered_row = table.splitlines()[1:3]

    assert "QUOTA RESETS" in header and "2, next expires in 5d 4h" in rendered_row
