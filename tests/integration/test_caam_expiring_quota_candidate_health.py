"""Live-verification and usable-allowance guards for drain candidates."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
from test_caam_expiring_quota_drain import NOW, RotationHarness, usage

__all__: list[str] = []

pytestmark = pytest.mark.integration


def test_scenario_a_candidate_that_is_not_live_verified_does_not_attract_a_drain(
    *, tmp_path: Path
) -> None:
    candidate = usage(seven_day_remaining=70.0, seven_day_reset_s=86_400.0)
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "candidate": candidate,
        },
        failed_profiles={"candidate"},
    )
    harness.seed_state(
        state={
            "profiles": {
                "candidate": {
                    "at": NOW,
                    **asdict(candidate),
                }
            }
        }
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []


def test_scenario_a_candidate_with_no_weekly_allowance_does_not_attract_a_drain(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "candidate": usage(seven_day_remaining=0.0, seven_day_reset_s=86_400.0),
        },
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []
