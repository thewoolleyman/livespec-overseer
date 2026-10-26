"""Integration scenarios for the weekly-reserve serveability decision.

These scenarios drive the shipped scheduled rotation pass.  The harness injects
only the provider usage responses and lets the pass retain its own selection,
capacity, and switch state.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from caam_decision import UsageRecord
from caam_decision_models import ExtraUsage
from test_caam_fast_drain import LARGE_PLAN, NOW, RotationHarness, usage

__all__: list[str] = []

pytestmark = pytest.mark.integration


def spend_blocked_usage(*, seven_day_remaining: float) -> UsageRecord:
    """A provider reading whose reached paid cap cannot bridge an empty short window."""
    base = usage(five_hour_remaining=0.0, seven_day_remaining=seven_day_remaining)
    return UsageRecord(
        five_hour_remaining=base.five_hour_remaining,
        seven_day_remaining=base.seven_day_remaining,
        five_hour_resets_at=base.five_hour_resets_at,
        seven_day_resets_at=base.seven_day_resets_at,
        fable_remaining=base.fable_remaining,
        fable_resets_at=base.fable_resets_at,
        extra_usage=ExtraUsage(
            is_enabled=False,
            spend_limit_reached=True,
            monthly_limit=100.0,
            used_credits=100.0,
        ),
    )


def test_scenario_the_weekly_reserve_is_released_when_no_account_above_it_can_serve(
    *, tmp_path: Path
) -> None:
    """A spend-blocked active account and an above-reserve account at the short
    floor leave no usable unprotected account above the reserve.

    The accounts below the reserve are otherwise healthy.  A scheduled rotation
    must therefore release the reserve and choose one of them instead of holding
    on the pre-release empty candidate set.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="spend-blocked",
        usages={
            "spend-blocked": spend_blocked_usage(seven_day_remaining=70.0),
            "at-short-floor": usage(five_hour_remaining=15.0, seven_day_remaining=70.0),
            "below-reserve": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={
            "spend-blocked": LARGE_PLAN,
            "at-short-floor": LARGE_PLAN,
            "below-reserve": LARGE_PLAN,
        },
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["below-reserve"]
    released = next(line for line in lines if "weekly reserve was released" in line)
    assert "spend-blocked" in released
    assert "at-short-floor" in released
