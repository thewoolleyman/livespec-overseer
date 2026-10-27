"""Integration coverage for weekly-reserve release by serveability.

The scheduled rotation pass receives provider usage only; its normal selection
and switching seams decide whether a released reserve reaches a destination.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from caam_decision import UsageRecord
from caam_decision_models import ExtraUsage
from test_caam_fast_drain import LARGE_PLAN, NOW, PASS_INTERVAL, RotationHarness, usage

__all__: list[str] = []

pytestmark = pytest.mark.integration


def spend_blocked_usage(*, weekly: float) -> UsageRecord:
    """A capped account whose exhausted included window cannot serve now."""
    base = usage(five_hour_remaining=0.0, seven_day_remaining=weekly)
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
    """An unusable above-reserve account must not strand healthy lower accounts."""
    harness = RotationHarness(
        home=tmp_path,
        active="spend-blocked",
        usages={
            "spend-blocked": spend_blocked_usage(weekly=70.0),
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


def test_scenario_a_release_on_serveability_grounds_does_not_release_a_protection_floor(
    *, tmp_path: Path
) -> None:
    """A released fleet reserve must retain every account-specific floor."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=15.0, seven_day_remaining=70.0),
            "protected": usage(five_hour_remaining=90.0, seven_day_remaining=90.0),
        },
        live_plans={"active": LARGE_PLAN, "protected": LARGE_PLAN},
    )

    code, lines = harness.run(
        at=NOW,
        scheduled=True,
        protected_accounts=(("protected", "90"),),
    )

    assert code == 0
    assert harness.switches == []
    assert any("weekly reserve was released" in line for line in lines)
    assert any("protected account floors reached" in line for line in lines)


def test_scenario_the_weekly_reserve_stays_in_force_while_an_account_above_it_can_serve(
    *, tmp_path: Path
) -> None:
    """A usable unprotected account above the reserve keeps lower accounts out."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=15.0, seven_day_remaining=70.0),
            "above": usage(five_hour_remaining=90.0, seven_day_remaining=70.0),
            "below": usage(five_hour_remaining=95.0, seven_day_remaining=8.0),
        },
        live_plans={"active": LARGE_PLAN, "above": LARGE_PLAN, "below": LARGE_PLAN},
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["above"]
    assert not any("weekly reserve was released" in line for line in lines)


def test_scenario_an_account_above_the_reserve_that_lacks_the_margin_releases_it(
    *, tmp_path: Path
) -> None:
    """The reserve cannot be defended by an account that fails the compared margin."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=15.0, seven_day_remaining=70.0),
            "above": usage(five_hour_remaining=20.0, seven_day_remaining=70.0),
            "below": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={"active": LARGE_PLAN, "above": LARGE_PLAN, "below": LARGE_PLAN},
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["below"]
    assert any("weekly reserve was released" in line and "above" in line for line in lines)


def test_scenario_an_active_account_projected_to_reach_the_floor_releases_the_reserve(
    *, tmp_path: Path
) -> None:
    """Fast drain makes an otherwise healthy active account unusable for the reserve."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=75.0, seven_day_remaining=70.0),
            "below": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={"active": LARGE_PLAN, "below": LARGE_PLAN},
    )

    first_code, _first_lines = harness.run(at=NOW, scheduled=True)
    harness.read(
        name="active",
        record=usage(five_hour_remaining=36.0, seven_day_remaining=70.0),
    )
    code, lines = harness.run(at=NOW + PASS_INTERVAL, scheduled=True)

    assert first_code == 0
    assert code == 0
    assert harness.switches == ["below"]
    assert any("weekly reserve was released" in line and "active" in line for line in lines)


def test_scenario_a_refusal_held_account_above_the_reserve_releases_it(*, tmp_path: Path) -> None:
    """A refusal-held non-active account is not available to defend the reserve."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=15.0, seven_day_remaining=8.0),
            "above": usage(five_hour_remaining=90.0, seven_day_remaining=70.0),
            "below": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={"active": LARGE_PLAN, "above": LARGE_PLAN, "below": LARGE_PLAN},
    )
    harness.seed_state(state={})
    harness.remember_refusal(
        account="above",
        recorded_at=NOW - 60.0,
        resets_at_epoch=NOW + 10 * PASS_INTERVAL,
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["below"]
    assert any("weekly reserve was released" in line and "above" in line for line in lines)


def test_scenario_an_account_above_the_reserve_that_is_not_live_verified_releases_it(
    *, tmp_path: Path
) -> None:
    """An unreadable provider usage row cannot keep healthy lower accounts reserved."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=80.0, seven_day_remaining=70.0),
            "unverified": usage(five_hour_remaining=90.0, seven_day_remaining=70.0),
            "below": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={"active": LARGE_PLAN, "unverified": LARGE_PLAN, "below": LARGE_PLAN},
    )

    first_code, _first_lines = harness.run(at=NOW, scheduled=True)
    harness.read(
        name="active",
        record=usage(five_hour_remaining=15.0, seven_day_remaining=8.0),
    )
    harness.failed_profiles.add("unverified")
    code, lines = harness.run(at=NOW + PASS_INTERVAL, scheduled=True)

    assert first_code == 0
    assert code == 0
    assert harness.switches == ["below"]
    assert any("weekly reserve was released" in line and "unverified" in line for line in lines)


def test_scenario_a_protected_account_above_the_reserve_does_not_keep_it_in_force(
    *, tmp_path: Path
) -> None:
    """A protected account cannot consume the fleet-wide reserve's eligibility role."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=15.0, seven_day_remaining=8.0),
            "protected": usage(five_hour_remaining=90.0, seven_day_remaining=90.0),
            "below": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={"active": LARGE_PLAN, "protected": LARGE_PLAN, "below": LARGE_PLAN},
    )

    code, lines = harness.run(
        at=NOW,
        scheduled=True,
        protected_accounts=(("protected", "80"),),
    )

    assert code == 0
    assert harness.switches == ["below"]
    assert any("no unprotected account is above it" in line for line in lines)
