"""Integration scenarios for provider usage windows that are not present."""

from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from caam_burn_rate import SHORT_WINDOW_BASELINE
from caam_usage import fetch_usage
from test_caam_fast_drain import LARGE_PLAN, NOW, RotationHarness, usage

__all__: list[str] = []

pytestmark = pytest.mark.integration


class UsageResponse:
    def __init__(self, *, body: bytes) -> None:
        self._body = io.BytesIO(body)

    def __enter__(self) -> UsageResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


def no_short_window_usage(*, tmp_path: Path):
    credentials = tmp_path / "usage-credentials.json"
    credentials.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token", "expiresAt": 1_900_000_000_000}}),
        encoding="utf-8",
    )

    def transport(*, request: object, timeout: float) -> UsageResponse:
        del request, timeout
        return UsageResponse(
            body=json.dumps(
                {
                    "five_hour": None,
                    "seven_day": {
                        "utilization": 95.0,
                        "resets_at": "2027-01-22T00:00:00Z",
                    },
                    "limits": [],
                }
            ).encode()
        )

    record, why = fetch_usage(creds_path=credentials, now=NOW, transport=transport)

    assert why is None
    assert record is not None
    return record


def unrecognised_limit_usage(*, tmp_path: Path):
    credentials = tmp_path / "usage-credentials.json"
    credentials.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token", "expiresAt": 1_900_000_000_000}}),
        encoding="utf-8",
    )

    def transport(*, request: object, timeout: float) -> UsageResponse:
        del request, timeout
        return UsageResponse(
            body=json.dumps(
                {
                    "five_hour": {
                        "utilization": 10.0,
                        "resets_at": "2027-01-21T00:00:00Z",
                    },
                    "seven_day": {
                        "utilization": 20.0,
                        "resets_at": "2027-01-22T00:00:00Z",
                    },
                    "limits": [
                        {
                            "kind": "provider_special",
                            "percent": 100.0,
                            "resets_at": "2027-01-23T00:00:00Z",
                        }
                    ],
                }
            ).encode()
        )

    record, why = fetch_usage(creds_path=credentials, now=NOW, transport=transport)

    assert why is None
    assert record is not None
    return record


def test_scenario_an_unrecognised_limit_leaves_the_account_readable_and_is_shown(
    *, tmp_path: Path
) -> None:
    active = unrecognised_limit_usage(tmp_path=tmp_path)
    harness = RotationHarness(
        home=tmp_path / "pass",
        active="active",
        usages={
            "active": active,
            "candidate": usage(five_hour_remaining=90.0, seven_day_remaining=80.0),
        },
        live_plans={"active": LARGE_PLAN, "candidate": LARGE_PLAN},
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert active.unrecognised_limits == (("provider_special", 0.0, "2027-01-23T00:00:00Z"),)
    assert code == 0
    assert harness.switches == []
    assert any("provider_special 0%" in line for line in lines)


def test_only_unrecognised_limits_do_not_make_a_usage_response_readable(*, tmp_path: Path) -> None:
    credentials = tmp_path / "usage-credentials.json"
    credentials.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token", "expiresAt": 1_900_000_000_000}}),
        encoding="utf-8",
    )

    def transport(*, request: object, timeout: float) -> UsageResponse:
        del request, timeout
        return UsageResponse(
            body=json.dumps(
                {
                    "limits": [
                        {
                            "kind": "provider_special",
                            "percent": 0.0,
                            "resets_at": "2027-01-23T00:00:00Z",
                        }
                    ]
                }
            ).encode()
        )

    record, why = fetch_usage(creds_path=credentials, now=NOW, transport=transport)

    assert record is None
    assert why == "unexpected response shape"


def test_scenario_a_scheduled_pass_evaluates_an_active_account_with_no_short_window_limit(
    *, tmp_path: Path
) -> None:
    active = no_short_window_usage(tmp_path=tmp_path)
    harness = RotationHarness(
        home=tmp_path / "pass",
        active="active",
        usages={
            "active": active,
            "weekly-reserve": usage(five_hour_remaining=90.0, seven_day_remaining=80.0),
        },
        live_plans={"active": LARGE_PLAN, "weekly-reserve": LARGE_PLAN},
    )

    code, lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["weekly-reserve"]
    assert any("weekly" in line for line in lines)
    assert any("no short-window limit" in line for line in lines)


def test_scenario_an_account_with_no_short_window_limit_is_selected_on_short_window_rotation(
    *, tmp_path: Path
) -> None:
    target = no_short_window_usage(tmp_path=tmp_path)
    harness = RotationHarness(
        home=tmp_path / "pass",
        active="at-short-floor",
        usages={
            "at-short-floor": usage(five_hour_remaining=15.0, seven_day_remaining=80.0),
            "no-short-window": target,
        },
        live_plans={"at-short-floor": LARGE_PLAN, "no-short-window": LARGE_PLAN},
    )

    code, _lines = harness.run(at=NOW, scheduled=True)

    assert code == 0
    assert harness.switches == ["no-short-window"]


def test_scenario_a_temporary_short_window_limit_is_honoured_only_on_the_readings_that_report_it(
    *, tmp_path: Path
) -> None:
    no_short_window = replace(
        no_short_window_usage(tmp_path=tmp_path),
        seven_day_remaining=80.0,
    )
    harness = RotationHarness(
        home=tmp_path / "pass",
        active="active",
        usages={
            "active": no_short_window,
            "spare": usage(five_hour_remaining=90.0, seven_day_remaining=80.0),
        },
        live_plans={"active": LARGE_PLAN, "spare": LARGE_PLAN},
    )

    first_code, _first_lines = harness.run(at=NOW, scheduled=True)

    assert first_code == 0
    assert harness.switches == []
    assert SHORT_WINDOW_BASELINE not in harness.read_state()

    harness.read(name="active", record=usage(five_hour_remaining=15.0, seven_day_remaining=80.0))
    second_code, second_lines = harness.run(at=NOW + 1_800.0, scheduled=True)

    assert second_code == 0
    assert harness.switches == ["spare"]
    assert any("5-hour window" in line for line in second_lines)

    harness.hand_switch(to="active")
    harness.read(name="active", record=no_short_window)
    third_code, third_lines = harness.run(at=NOW + 3_600.0, scheduled=True)

    assert third_code == 0
    assert harness.switches == ["spare"]
    assert all("projected short-window drain" not in line for line in third_lines)
    baseline = harness.read_state()[SHORT_WINDOW_BASELINE]
    assert isinstance(baseline, dict)
    assert baseline["remaining"] == 15.0
