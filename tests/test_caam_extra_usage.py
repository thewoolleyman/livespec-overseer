"""Tests for reading the extra-usage DOLLAR meter the usage response carries.

The meter is the pay-as-you-go overage that rides on a Max account beside its
included quota, and this operation used to parse the same response and throw
every one of its fields away. These tests pin the reading itself; what the
reading MEANS for selection is pinned by `test_caam_spend_limit_rotation`.
"""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
from types import ModuleType

__all__: list[str] = []


CAPPED_BLOCK: dict[str, object] = {
    "is_enabled": False,
    "spend_limit_reached": True,
    "monthly_limit": 100.0,
    "used_credits": 107.37,
}
ARMED_BLOCK: dict[str, object] = {
    "is_enabled": True,
    "spend_limit_reached": False,
    "monthly_limit": 40.0,
    "used_credits": 27.5,
}
NEVER_ENABLED_BLOCK: dict[str, object] = {
    "is_enabled": False,
    "spend_limit_reached": False,
    "monthly_limit": None,
    "used_credits": None,
}


def extra_usage_module() -> ModuleType:
    """The dollar-meter reader, asserted present before anything imports it."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_extra_usage.py"
    assert module_path.is_file()
    return importlib.import_module("caam_extra_usage")


def meter(*, block: dict[str, object] | None) -> object:
    module = extra_usage_module()
    body: dict[str, object] = {} if block is None else {"extra_usage": block}
    return module.extra_usage_from(body=body)


def record(*, block: dict[str, object] | None) -> object:
    models = importlib.import_module("caam_decision_models")
    return models.UsageRecord(
        five_hour_remaining=50.0,
        seven_day_remaining=50.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
        extra_usage=meter(block=block),
    )


class Response:
    def __init__(self, *, body: bytes) -> None:
        self._body = io.BytesIO(body)

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


def poll(*, tmp_path: Path, body: dict[str, object]) -> object:
    """Drive the real polling path so the record under test came off the wire."""
    creds = tmp_path / ".credentials.json"
    creds.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "tok", "expiresAt": 9_000_000}}),
        encoding="utf-8",
    )

    def transport(*, request: object, timeout: float) -> Response:
        del request, timeout
        return Response(body=json.dumps(body).encode())

    usage, why = importlib.import_module("caam_usage").fetch_usage(
        creds_path=creds, now=1000.0, transport=transport
    )
    assert why is None
    return usage


def test_the_extra_usage_block_is_read_off_the_response() -> None:
    parsed = meter(block=CAPPED_BLOCK)

    assert parsed is not None
    assert parsed.is_enabled is False
    assert parsed.spend_limit_reached is True
    assert parsed.monthly_limit == 100.0
    assert parsed.used_credits == 107.37


def test_a_response_carrying_no_extra_usage_block_reads_as_no_meter() -> None:
    """Absence is a different fact from a meter reading zero, and stays distinct."""
    assert meter(block=None) is None


def test_minor_unit_figures_are_scaled_to_dollars_by_decimal_places() -> None:
    """The live response reports MINOR units (cents), not dollars.

    Measured live 2026-09-10: `used_credits: 10737, monthly_limit: 10000,
    decimal_places: 2` against an account the operator confirmed had actually
    spent about $107 of a $100 cap. Reading the raw figures as already-dollars
    printed an ALERT reading $10737.00 spent of $10000.00 -- two orders of
    magnitude too high, and exactly the scale `decimal_places` names.
    """
    parsed = meter(
        block={
            "is_enabled": False,
            "spend_limit_reached": True,
            "monthly_limit": 10000,
            "used_credits": 10737.0,
            "decimal_places": 2,
        }
    )

    assert parsed is not None
    assert parsed.monthly_limit == 100.0
    assert parsed.used_credits == 107.37


def test_a_missing_decimal_places_leaves_the_raw_figure_unscaled() -> None:
    """No reported scale means the figure is already in its major unit.

    This is the ordinary reading for the fixtures elsewhere in this file, which
    predate `decimal_places` shipping on the response and carry raw dollar
    floats directly -- scaling them would be inventing a factor the response
    never reported.
    """
    parsed = meter(block={"monthly_limit": 40.0, "used_credits": 12.0})

    assert parsed is not None
    assert parsed.monthly_limit == 40.0
    assert parsed.used_credits == 12.0


def test_a_non_boolean_flag_reads_as_false_rather_than_as_truthy() -> None:
    """Fail-closed: only a literal `true` arms a flag that can license dollar spend."""
    parsed = meter(block={"is_enabled": "yes", "spend_limit_reached": 1})

    assert parsed is not None
    assert parsed.is_enabled is False
    assert parsed.spend_limit_reached is False


def test_window_dollar_figures_are_read_when_a_window_reports_them() -> None:
    module = extra_usage_module()

    dollars = module.window_dollars_from(
        window={"limit_dollars": 40.0, "used_dollars": 12.0, "remaining_dollars": 28.0}
    )

    assert dollars is not None
    assert (dollars.limit, dollars.used, dollars.remaining) == (40.0, 12.0, 28.0)


def test_a_window_reporting_no_dollars_at_all_yields_no_dollar_record() -> None:
    """Every window is null-valued on a Max plan, so this is the ordinary answer."""
    module = extra_usage_module()

    assert module.window_dollars_from(window={"utilization": 12.5}) is None


def test_spend_capped_is_true_only_for_an_account_that_hit_its_cap() -> None:
    module = extra_usage_module()

    assert module.spend_capped(usage=None) is False
    assert module.spend_capped(usage=record(block=None)) is False
    assert module.spend_capped(usage=record(block=ARMED_BLOCK)) is False
    assert module.spend_capped(usage=record(block=CAPPED_BLOCK)) is True


def test_spending_dollars_keys_on_dollars_spent_not_on_the_enabled_flag() -> None:
    """The flag and the spend disagree in BOTH directions, and the spend is the fact."""
    module = extra_usage_module()

    assert module.spending_dollars(extra_usage=None) is False
    assert module.spending_dollars(extra_usage=meter(block=NEVER_ENABLED_BLOCK)) is False
    # Armed but untouched: enabled, nothing spent, so nothing to alert about.
    assert (
        module.spending_dollars(extra_usage=meter(block={"is_enabled": True, "used_credits": 0.0}))
        is False
    )
    # Auto-disabled on reaching its cap: the flag reads false while every dollar is gone.
    assert module.spending_dollars(extra_usage=meter(block=CAPPED_BLOCK)) is True


def test_dollars_left_reports_the_cap_balance_in_the_remaining_direction() -> None:
    module = extra_usage_module()

    assert module.dollars_left(extra_usage=meter(block=ARMED_BLOCK)) == 12.5


def test_dollars_left_never_reports_a_negative_balance() -> None:
    """A cap can be overshot inside one request -- measured at $107.37 against $100."""
    module = extra_usage_module()

    assert module.dollars_left(extra_usage=meter(block=CAPPED_BLOCK)) == 0.0


def test_dollars_left_is_absent_when_there_is_no_cap_to_measure_against() -> None:
    module = extra_usage_module()

    assert module.dollars_left(extra_usage=None) is None
    assert module.dollars_left(extra_usage=meter(block=NEVER_ENABLED_BLOCK)) is None


def test_dollars_left_treats_an_unreported_spend_as_nothing_spent() -> None:
    module = extra_usage_module()

    assert module.dollars_left(extra_usage=meter(block={"monthly_limit": 40.0})) == 40.0


def test_a_polled_usage_record_carries_the_meter_the_response_reported(tmp_path: Path) -> None:
    """The wiring: the SAME response caam already fetches, no second endpoint."""
    usage = poll(
        tmp_path=tmp_path,
        body={
            "five_hour": {
                "utilization": 12.5,
                "resets_at": "2026-09-08T12:00:00Z",
                "limit_dollars": 40.0,
                "used_dollars": 12.0,
                "remaining_dollars": 28.0,
            },
            "seven_day": {"utilization": 34.5, "resets_at": "2026-09-12T12:00:00Z"},
            "limits": [],
            "extra_usage": CAPPED_BLOCK,
        },
    )

    assert usage is not None
    assert usage.extra_usage is not None
    assert usage.extra_usage.spend_limit_reached is True
    assert usage.extra_usage.monthly_limit == 100.0
    assert usage.five_hour_dollars is not None
    assert usage.five_hour_dollars.remaining == 28.0
    assert usage.seven_day_dollars is None


def test_a_polled_record_from_a_response_without_the_meter_carries_none(tmp_path: Path) -> None:
    usage = poll(
        tmp_path=tmp_path,
        body={
            "five_hour": {"utilization": 12.5, "resets_at": "2026-09-08T12:00:00Z"},
            "seven_day": {"utilization": 34.5, "resets_at": "2026-09-12T12:00:00Z"},
            "limits": [],
        },
    )

    assert usage is not None
    assert usage.extra_usage is None
    assert usage.five_hour_dollars is None
