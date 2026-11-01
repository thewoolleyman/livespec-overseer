"""Integration scenarios for provider usage windows that are not present."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
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
