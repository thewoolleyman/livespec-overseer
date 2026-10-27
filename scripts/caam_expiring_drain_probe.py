"""Replay the expiring-quota drain exception through the scheduled pass."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import test_caam_expiring_quota_candidate_health as scenarios
from test_caam_expiring_quota_drain import RotationHarness

__all__: list[str] = []


def main() -> None:
    """Run the below-reserve drain scenario and print its scheduled-pass result."""
    original_run = RotationHarness.run

    def observed_run(harness: RotationHarness, **kwargs: object) -> tuple[int, tuple[str, ...]]:
        code, lines = original_run(harness, **kwargs)
        sys.stdout.write(
            f"scheduled-pass case=expiring-drain exit={code} " f"switches={harness.switches}\n"
        )
        for line in lines:
            sys.stdout.write(line + "\n")
        return code, lines

    RotationHarness.run = observed_run
    with tempfile.TemporaryDirectory(prefix="expiring-drain-") as directory:
        scenarios.test_scenario_a_candidate_with_no_weekly_allowance_does_not_attract_a_drain(
            tmp_path=Path(directory)
        )


if __name__ == "__main__":
    main()
