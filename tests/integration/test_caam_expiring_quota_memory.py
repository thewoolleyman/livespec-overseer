"""Durable short-window departure guards for the expiring-quota drain."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_caam_expiring_quota_drain import RotationHarness, reset_at, usage

__all__: list[str] = []

pytestmark = pytest.mark.integration


def test_scenario_an_account_left_on_its_short_window_is_not_drained_back_before_reset(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="departing",
        usages={
            "departing": usage(
                five_hour_remaining=10.0,
                five_hour_reset_s=3_600.0,
                seven_day_reset_s=86_400.0,
            ),
            "destination": usage(seven_day_reset_s=604_800.0),
        },
    )

    first_code, _first_lines = harness.run()
    harness.usages["departing"] = usage(
        five_hour_remaining=80.0,
        five_hour_reset_s=3_600.0,
        seven_day_reset_s=86_400.0,
    )
    second_code, _second_lines = harness.run()

    assert first_code == second_code == 0
    assert harness.switches == ["destination"]
    assert harness.read_state()["short_window_departures"] == {
        "departing": {"resets_at": reset_at(seconds_from_now=3_600.0)}
    }


def test_scenario_without_a_reported_reset_an_account_waits_for_full_replenishment(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="departing",
        usages={
            "departing": usage(
                five_hour_remaining=10.0,
                five_hour_reset_s=None,
                seven_day_reset_s=86_400.0,
            ),
            "destination": usage(seven_day_reset_s=604_800.0),
        },
    )

    first_code, _first_lines = harness.run()
    harness.usages["departing"] = usage(
        five_hour_remaining=99.0,
        five_hour_reset_s=None,
        seven_day_reset_s=86_400.0,
    )
    held_code, _held_lines = harness.run()
    assert held_code == 0
    assert harness.switches == ["destination"]
    harness.usages["departing"] = usage(
        five_hour_remaining=100.0,
        five_hour_reset_s=None,
        seven_day_reset_s=86_400.0,
    )
    released_code, _released_lines = harness.run()

    assert first_code == released_code == 0
    assert harness.switches == ["destination", "departing"]
    assert harness.read_state()["short_window_departures"] == {"departing": {"resets_at": None}}


def test_scenario_a_move_on_several_triggers_including_short_window_is_remembered(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="departing",
        usages={
            "departing": usage(
                five_hour_remaining=10.0,
                seven_day_remaining=5.0,
                five_hour_reset_s=3_600.0,
                seven_day_reset_s=86_400.0,
            ),
            "destination": usage(seven_day_reset_s=604_800.0),
        },
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == ["destination"]
    assert harness.read_state()["short_window_departures"] == {
        "departing": {"resets_at": reset_at(seconds_from_now=3_600.0)}
    }
