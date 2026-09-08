"""Tests for the operator-facing surfaces of the extra-usage dollar meter.

The incident this closes was SILENT: the fleet sat on a spend-capped account for
hours while the printed table showed healthy percentages and nothing anywhere
said a dollar had been spent. So the meter owes two surfaces -- a column in the
table and an ALERT line -- and both are pinned here.
"""

from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path
from types import ModuleType

__all__: list[str] = []


CAPPED_BLOCK: dict[str, object] = {
    "is_enabled": False,
    "spend_limit_reached": True,
    "monthly_limit": 100.0,
    "used_credits": 107.37,
}
SPENDING_BLOCK: dict[str, object] = {
    "is_enabled": True,
    "spend_limit_reached": False,
    "monthly_limit": 40.0,
    "used_credits": 27.5,
}
ARMED_UNSPENT_BLOCK: dict[str, object] = {
    "is_enabled": True,
    "spend_limit_reached": False,
    "monthly_limit": 40.0,
    "used_credits": 0.0,
}
NEVER_ENABLED_BLOCK: dict[str, object] = {
    "is_enabled": False,
    "spend_limit_reached": False,
    "monthly_limit": None,
    "used_credits": None,
}


def spend_report_module() -> ModuleType:
    """The meter's reporting surfaces, asserted present before anything imports it."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_spend_report.py"
    assert module_path.is_file()
    return importlib.import_module("caam_spend_report")


def meter(*, block: dict[str, object] | None) -> object:
    module = importlib.import_module("caam_extra_usage")
    body: dict[str, object] = {} if block is None else {"extra_usage": block}
    return module.extra_usage_from(body=body)


def profile(*, name: str, block: dict[str, object] | None, source: str = "live") -> object:
    models = importlib.import_module("caam_decision_models")
    return models.ProfileUsage(
        name=name,
        source=source,
        usage=models.UsageRecord(
            five_hour_remaining=80.0,
            seven_day_remaining=70.0,
            five_hour_resets_at="2026-09-08T14:30:00Z",
            seven_day_resets_at="2026-09-10T15:12:00Z",
            fable_remaining=None,
            fable_resets_at=None,
            extra_usage=meter(block=block),
        ),
    )


def dark_profile(*, name: str) -> object:
    models = importlib.import_module("caam_decision_models")
    return models.ProfileUsage(name=name, source="dark: no token", usage=None)


class Flags:
    def __init__(self) -> None:
        self.dry_run = False
        self.no_models = False
        self.session_models: tuple[tuple[str, str], ...] = ()
        self.protected_accounts: tuple[tuple[str, str], ...] = ()


class Context:
    def __init__(self, *, home: Path) -> None:
        self.flags = Flags()
        self.home = home
        self.now = 1_788_000_000.0
        self.state: dict[str, object] = {}
        self.state_path = home / "state.json"
        self.span = None
        self.lines: list[str] = []

    def stdout(self, line: str) -> None:
        self.lines.append(line)


def test_the_table_cells_name_the_meter_state_and_what_its_cap_has_left() -> None:
    module = spend_report_module()

    assert module.extra_usage_cells(extra_usage=meter(block=CAPPED_BLOCK)) == ("CAPPED", "$0.00")
    assert module.extra_usage_cells(extra_usage=meter(block=SPENDING_BLOCK)) == ("on", "$12.50")
    assert module.extra_usage_cells(extra_usage=meter(block=NEVER_ENABLED_BLOCK)) == ("off", "-")


def test_an_account_with_no_meter_reading_renders_as_no_reading() -> None:
    module = spend_report_module()

    assert module.extra_usage_cells(extra_usage=None) == ("-", "-")


def test_the_rendered_table_carries_the_extra_usage_columns() -> None:
    module = spend_report_module()
    assert module is not None
    rendering = importlib.import_module("caam_rendering")
    now = datetime.fromisoformat("2026-09-08T12:00:00+00:00")

    table = rendering.render_table(
        rows=(
            profile(name="anthropic-0", block=CAPPED_BLOCK),
            profile(name="anthropic-2", block=SPENDING_BLOCK),
            dark_profile(name="anthropic-9"),
        ),
        active_name="anthropic-0",
        now=now,
    )
    header, capped_row, spending_row, dark_row = table.splitlines()[1:5]

    assert "EXTRA" in header
    assert "$ LEFT" in header
    assert capped_row.split()[-3:] == ["CAPPED", "$0.00", "live"]
    assert spending_row.split()[-3:] == ["on", "$12.50", "snapshot"]
    # A row with no usage at all reports no meter reading rather than "off".
    assert dark_row.split()[-5:] == ["-", "-", "dark:", "no", "token"]


def test_a_capped_account_raises_an_alert_naming_the_spend_limit() -> None:
    module = spend_report_module()

    lines = module.spend_alert_lines(profiles=(profile(name="anthropic-0", block=CAPPED_BLOCK),))

    assert len(lines) == 1
    assert lines[0].startswith("ALERT: anthropic-0 ")
    assert "spend limit" in lines[0]
    assert "$107.37" in lines[0]
    assert "$100.00" in lines[0]


def test_an_account_actively_spending_dollars_raises_an_alert_naming_what_is_left() -> None:
    """Fires on the FIRST dollar, which is strictly earlier than nearing the cap."""
    module = spend_report_module()

    lines = module.spend_alert_lines(profiles=(profile(name="anthropic-2", block=SPENDING_BLOCK),))

    assert len(lines) == 1
    assert "is spending pay-as-you-go dollars" in lines[0]
    assert "$27.50" in lines[0]
    assert "$12.50" in lines[0]


def test_no_account_spending_dollars_raises_no_alert_at_all() -> None:
    """The quiet case must stay quiet: an armed-but-unspent account is not news."""
    module = spend_report_module()

    assert (
        module.spend_alert_lines(
            profiles=(
                profile(name="anthropic-1", block=None),
                profile(name="anthropic-3", block=NEVER_ENABLED_BLOCK),
                profile(name="anthropic-4", block=ARMED_UNSPENT_BLOCK),
                dark_profile(name="anthropic-9"),
            )
        )
        == ()
    )


def test_an_alert_with_no_cap_reported_still_names_the_account() -> None:
    module = spend_report_module()

    lines = module.spend_alert_lines(
        profiles=(profile(name="anthropic-5", block={"used_credits": 3.0}),)
    )

    assert len(lines) == 1
    assert "unknown" in lines[0]


def test_the_pass_status_output_carries_the_alert(tmp_path: Path) -> None:
    """The wiring: an operator reading a pass sees the alert beside the table."""
    module = spend_report_module()
    assert module is not None
    status = importlib.import_module("caam_anthropic_status")
    models = importlib.import_module("caam_decision_models")
    context = Context(home=tmp_path)
    rows = (
        profile(name="anthropic-0", block=CAPPED_BLOCK),
        profile(name="anthropic-1", block=None),
    )
    current = rows[1].usage
    assert isinstance(current, models.UsageRecord)

    status.write_status(
        context=context,
        profiles=rows,
        active_name="anthropic-1",
        current=current,
        enforce_models=lambda **kwargs: [],
    )

    alerts = [line for line in context.lines if line.startswith("ALERT: ")]
    assert len(alerts) == 1
    assert alerts[0].startswith("ALERT: anthropic-0 ")
