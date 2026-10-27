"""Replay weekly-reserve scenarios through the shipped scheduled pass."""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import test_caam_weekly_reserve_release as scenarios
from test_caam_fast_drain import RotationHarness

__all__: list[str] = []

Scenario = Callable[..., None]

CASES: dict[str, Scenario] = {
    "unusable": (
        scenarios.test_scenario_the_weekly_reserve_is_released_when_no_account_above_it_can_serve
    ),
    "positive-below-floor": (
        scenarios.test_scenario_a_released_reserve_admits_a_positive_below_floor_candidate
    ),
    "protected-spend": (
        scenarios.test_scenario_a_protected_spend_blocked_active_releases_an_exhausted_reserve
    ),
    "protection": (
        scenarios.test_scenario_a_release_on_serveability_grounds_does_not_release_a_protection_floor
    ),
    "enforced": (
        scenarios.test_scenario_the_weekly_reserve_stays_in_force_while_an_account_above_it_can_serve
    ),
    "margin": (
        scenarios.test_scenario_an_account_above_the_reserve_that_lacks_the_margin_releases_it
    ),
    "capacity": (
        scenarios.test_scenario_an_above_reserve_candidate_that_fails_capacity_releases_the_reserve
    ),
    "fast-drain": (
        scenarios.test_scenario_an_active_account_projected_to_reach_the_floor_releases_the_reserve
    ),
    "refusal": scenarios.test_scenario_a_refusal_held_account_above_the_reserve_releases_it,
    "refusal-capacity": (
        scenarios.test_scenario_reserve_release_precedes_the_refusal_capacity_release
    ),
    "scoped": scenarios.test_scenario_the_scoped_margin_exception_does_not_keep_the_reserve,
    "unverified": (
        scenarios.test_scenario_an_account_above_the_reserve_that_is_not_live_verified_releases_it
    ),
    "protected": (
        scenarios.test_scenario_a_protected_account_above_the_reserve_does_not_keep_it_in_force
    ),
}


def main() -> None:
    """Run one named provider-usage scenario and print the scheduled-pass result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=sorted(CASES))
    arguments = parser.parse_args()
    original_run = RotationHarness.run

    def observed_run(harness: RotationHarness, **kwargs: object) -> tuple[int, tuple[str, ...]]:
        code, lines = original_run(harness, **kwargs)
        sys.stdout.write(
            f"scheduled-pass case={arguments.case} exit={code} " f"switches={harness.switches}\n"
        )
        for line in lines:
            sys.stdout.write(line + "\n")
        return code, lines

    RotationHarness.run = observed_run
    with tempfile.TemporaryDirectory(prefix="weekly-reserve-") as directory:
        CASES[arguments.case](tmp_path=Path(directory))


if __name__ == "__main__":
    main()
