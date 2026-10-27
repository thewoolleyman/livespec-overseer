"""Integration coverage for weekly-reserve release by serveability.

The scheduled rotation pass receives provider usage only; its normal selection
and switching seams decide whether a released reserve reaches a destination.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from caam_capacity_load import FLEET_LOAD
from caam_decision import UsageRecord
from caam_decision_models import ExtraUsage
from test_caam_fast_drain import (
    LARGE_PLAN,
    NOW,
    PASS_INTERVAL,
    SMALL_PLAN,
    RotationHarness,
    usage,
)

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


def test_scenario_a_released_reserve_admits_a_positive_below_floor_candidate(
    *, tmp_path: Path
) -> None:
    """Release returns candidates to ordinary selection, not the rotation floor."""
    harness = RotationHarness(
        home=tmp_path,
        active="spend-blocked",
        usages={
            "spend-blocked": spend_blocked_usage(weekly=70.0),
            "at-short-floor": usage(five_hour_remaining=15.0, seven_day_remaining=70.0),
            "below-reserve": usage(five_hour_remaining=1.0, seven_day_remaining=8.0),
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
    assert any("weekly reserve was released" in line for line in lines)


def test_scenario_a_released_reserve_reaches_the_weekly_boundary_candidate(
    *, tmp_path: Path
) -> None:
    """Release leaves the weekly boundary to ordinary candidate selection."""
    harness = RotationHarness(
        home=tmp_path,
        active="spend-blocked",
        usages={
            "spend-blocked": spend_blocked_usage(weekly=70.0),
            "weekly-boundary": usage(five_hour_remaining=1.0, seven_day_remaining=10.0),
        },
        live_plans={
            "spend-blocked": LARGE_PLAN,
            "weekly-boundary": LARGE_PLAN,
        },
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["weekly-boundary"]
    assert any("weekly reserve was released" in line for line in lines)


def test_scenario_a_protected_spend_blocked_active_releases_an_exhausted_reserve(
    *, tmp_path: Path
) -> None:
    """The protected active and every other above-reserve account can be unusable.

    This is intentionally distinct from the general serveability case: the
    active's protection floor removes it from the accounts that could preserve
    the fleet-wide reserve, and its spend cap makes clear that the pass does
    not merely move because its own protection was reached.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="protected-spend-blocked",
        usages={
            "protected-spend-blocked": spend_blocked_usage(weekly=70.0),
            "exhausted-above": usage(five_hour_remaining=15.0, seven_day_remaining=70.0),
            "below-reserve": usage(five_hour_remaining=90.0, seven_day_remaining=8.0),
        },
        live_plans={
            "protected-spend-blocked": LARGE_PLAN,
            "exhausted-above": LARGE_PLAN,
            "below-reserve": LARGE_PLAN,
        },
    )

    code, lines = harness.run(
        at=NOW,
        scheduled=True,
        protected_accounts=(("protected-spend-blocked", "50"),),
    )

    assert code == 0
    assert harness.switches == ["below-reserve"]
    released = next(line for line in lines if "weekly reserve was released" in line)
    assert "exhausted-above" in released


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


def test_scenario_an_above_reserve_candidate_that_fails_capacity_releases_the_reserve(
    *, tmp_path: Path
) -> None:
    """An above-reserve account projected below the floor cannot defend the reserve.

    The first scheduled pass records a real provider-usage baseline.  On the
    second pass that measured fleet load would drain the small above-reserve
    candidate before the following pass, while the lower-reserve large account
    can carry it.  That makes the capacity predicate, rather than ranking, the
    observable reason the reserve is released.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=25.0, seven_day_remaining=70.0),
            "above-small": usage(five_hour_remaining=50.0, seven_day_remaining=70.0),
            "below-large": usage(five_hour_remaining=50.0, seven_day_remaining=8.0),
        },
        live_plans={
            "active": LARGE_PLAN,
            "above-small": SMALL_PLAN,
            "below-large": LARGE_PLAN,
        },
    )

    first_code, _first_lines = harness.run(at=NOW, scheduled=True)
    harness.read(name="active", record=usage(five_hour_remaining=15.0, seven_day_remaining=70.0))
    code, lines = harness.run(at=NOW + PASS_INTERVAL, scheduled=True)

    assert first_code == code == 0
    assert harness.switches == ["below-large"]
    assert any("weekly reserve was released" in line and "above-small" in line for line in lines)


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


def test_scenario_a_scoped_trigger_still_releases_a_fast_draining_active_reserve(
    *, tmp_path: Path
) -> None:
    """A higher-precedence scoped trigger cannot hide active fast drain."""
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(
                five_hour_remaining=75.0,
                seven_day_remaining=70.0,
                fable_remaining=80.0,
            ),
            "below": usage(
                five_hour_remaining=90.0,
                seven_day_remaining=8.0,
                fable_remaining=80.0,
            ),
        },
        live_plans={"active": LARGE_PLAN, "below": LARGE_PLAN},
    )
    harness.seed_state(state={"session_models": {"session": "fable"}})

    first_code, _first_lines = harness.run(at=NOW, scheduled=True)
    harness.read(
        name="active",
        record=usage(
            five_hour_remaining=36.0,
            seven_day_remaining=70.0,
            fable_remaining=0.0,
        ),
    )
    code, lines = harness.run(at=NOW + PASS_INTERVAL, scheduled=True)

    assert first_code == code == 0
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


def test_scenario_reserve_release_precedes_the_refusal_capacity_release(*, tmp_path: Path) -> None:
    """A refusal-held active releases the reserve before capacity's own release.

    Both candidates fail the normal capacity test under the remembered provider
    load.  The above-reserve candidate therefore cannot preserve the reserve;
    its release admits the lower one, and only then does the refusal-held
    capacity release select that lower account.  Reversing those two decisions
    leaves no lower-reserve candidate for the capacity exception to reach.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="refusing-active",
        usages={
            "refusing-active": usage(five_hour_remaining=60.0, seven_day_remaining=70.0),
            "above-small": usage(
                five_hour_remaining=50.0,
                seven_day_remaining=70.0,
                seven_day_reset_s=3 * 86_400.0,
            ),
            "below-small": usage(
                five_hour_remaining=50.0,
                seven_day_remaining=8.0,
                seven_day_reset_s=2 * 86_400.0,
            ),
        },
        live_plans={
            "refusing-active": LARGE_PLAN,
            "above-small": SMALL_PLAN,
            "below-small": SMALL_PLAN,
        },
    )
    harness.seed_state(state={FLEET_LOAD: {"load": 70.0 / PASS_INTERVAL, "at": NOW}})
    harness.remember_refusal(
        account="refusing-active",
        recorded_at=NOW - 60.0,
        resets_at_epoch=NOW + 10 * PASS_INTERVAL,
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["below-small"]
    assert any("weekly reserve was released" in line and "above-small" in line for line in lines)


def test_scenario_the_scoped_margin_exception_does_not_keep_the_reserve(*, tmp_path: Path) -> None:
    """The normal margin, not scoped waiver, establishes reserve serveability.

    The fable pin is a durable operator precondition; every scheduled pass
    receives only provider usage.  The above-reserve account can serve fable
    but clears the five-hour margin solely through the scoped exception, so it
    cannot defend the reserve.  The lower-reserve account clears the ordinary
    margin and is selected after the reserve is released.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(
                five_hour_remaining=80.0,
                seven_day_remaining=70.0,
                fable_remaining=0.0,
            ),
            "above-scoped": usage(
                five_hour_remaining=70.0,
                seven_day_remaining=70.0,
                fable_remaining=80.0,
                seven_day_reset_s=3 * 86_400.0,
            ),
            "below-ordinary": usage(
                five_hour_remaining=90.0,
                seven_day_remaining=8.0,
                fable_remaining=80.0,
                seven_day_reset_s=2 * 86_400.0,
            ),
        },
        live_plans={
            "active": LARGE_PLAN,
            "above-scoped": LARGE_PLAN,
            "below-ordinary": LARGE_PLAN,
        },
    )
    harness.seed_state(state={"session_models": {"session": "fable"}})

    code, lines = harness.run(
        at=NOW,
        scheduled=True,
        protected_accounts=(("active", "50"),),
    )

    assert code == 0
    assert harness.switches == ["below-ordinary"]
    assert any("weekly reserve was released" in line and "above-scoped" in line for line in lines)


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
    assert any("no unprotected account is above it" in line for line in lines)


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
