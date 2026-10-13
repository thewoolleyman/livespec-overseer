"""Eligibility guards for the expiring weekly-quota drain."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_caam_expiring_quota_drain import RotationHarness, usage

__all__: list[str] = []

pytestmark = pytest.mark.integration


def test_scenario_a_candidate_within_the_margin_of_the_weekly_reserve_does_not_attract_a_drain(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "candidate": usage(seven_day_remaining=19.0, seven_day_reset_s=86_400.0),
        },
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []


def test_scenario_a_protected_drain_destination_keeps_a_margin_above_its_own_floor(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "candidate": usage(seven_day_remaining=29.0, seven_day_reset_s=86_400.0),
        },
    )

    code, _lines = harness.run(
        protected_accounts=(("active", "5"), ("candidate", "20")),
    )

    assert code == 0
    assert harness.switches == []


def test_scenario_short_window_threshold_margin_prevents_a_drain(*, tmp_path: Path) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "candidate": usage(
                five_hour_remaining=24.0,
                seven_day_remaining=70.0,
                seven_day_reset_s=86_400.0,
            ),
        },
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []


def test_scenario_a_drain_keeps_a_satisfiable_scoped_pin_satisfiable(*, tmp_path: Path) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(fable_remaining=80.0, seven_day_reset_s=604_800.0),
            "candidate": usage(
                fable_remaining=24.0,
                seven_day_remaining=70.0,
                seven_day_reset_s=86_400.0,
            ),
        },
    )
    harness.seed_state(state={"session_models": {"worker": "fable"}})

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []
