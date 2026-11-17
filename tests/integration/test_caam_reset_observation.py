"""Integration-tier reset observation through the shipped rotation pass.

The pass reads each managed account's quota resets alongside its quota poll. The
reading is observation only: whatever it returns, fails or declines, the quota
report and the rotation decision stay exactly what they would have been without it.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import caam_rendering
import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import ProfileUsage, UsageRecord
from caam_resets import QuotaReset, ResetReading

from tests.integration.test_caam_capacity_reporting import (
    LARGE_PLAN,
    NOW,
    CapacityHarness,
    reset_at,
    usage,
)

__all__: list[str] = []

pytestmark = pytest.mark.integration

RECURRING = QuotaReset(
    program="juniper_tide",
    reset_id=None,
    clears=("five_hour",),
    uses_left=1,
    uses_total=1,
    lapses_at=None,
    usable_now=False,
    requires_limit=True,
)


@dataclass(kw_only=True)
class ResetHarness(CapacityHarness):
    """The capacity harness with a declared reset read per account."""

    live_resets: dict[str, ResetReading | None] = field(default_factory=dict)
    usage_reads: list[Path] = field(default_factory=list)
    reset_reads: list[Path] = field(default_factory=list)

    def run(self) -> tuple[int, tuple[str, ...]]:
        lines: list[str] = []
        code = run_pass(
            flags=Flags(
                scheduled=True,
                force=False,
                dry_run=False,
                no_models=True,
                no_warm=True,
                session_models=(),
                protected_accounts=(),
            ),
            home=self.home,
            now=NOW,
            stdout=lines.append,
            caam_runner=self.run_caam,
            fetcher=self.fetch_usage,
            capacity_source=self.read_plan,
            reset_source=self.read_resets,
            switch_account=self.switch_account,
            save_state=lambda *, state, state_path: None,
            enforce_models=lambda **kwargs: [],
        )
        return code, tuple(lines)

    def fetch_usage(
        self, *, creds_path: Path, now: float | None = None
    ) -> tuple[UsageRecord | None, str | None]:
        self.usage_reads.append(creds_path)
        return super().fetch_usage(creds_path=creds_path, now=now)

    def read_resets(
        self, *, creds_path: Path, now: float | None = None
    ) -> tuple[ResetReading | None, str | None]:
        del now
        self.reset_reads.append(creds_path)
        reading = self.live_resets.get(
            self._account_of(creds_path=creds_path), ResetReading(resets=())
        )
        if reading is None:
            return None, "HTTP 500"
        return reading, None


def harness_with(
    *, home: Path, live_resets: dict[str, ResetReading | None] | None = None
) -> ResetHarness:
    """An exhausted active account beside a healthy one, so the pass rotates."""
    return ResetHarness(
        home=home,
        active="anthropic-0",
        usages={
            "anthropic-0": usage(five_hour_remaining=1.0, seven_day_remaining=1.0),
            "anthropic-1": usage(),
        },
        live_plans={"anthropic-0": LARGE_PLAN, "anthropic-1": LARGE_PLAN},
        live_resets=live_resets or {},
    )


def test_every_pass_reads_each_accounts_resets_with_its_quota_poll_credential(
    *, tmp_path: Path
) -> None:
    """Each managed account's reset read opens the same credential its quota poll used."""
    harness = harness_with(home=tmp_path)

    code, _ = harness.run()

    assert code == 0
    assert harness.reset_reads, "the pass never read any account's resets"
    assert sorted(harness.reset_reads) == sorted(harness.usage_reads)


def test_a_reset_reading_that_fails_or_is_unreadable_changes_neither_report_nor_rotation(
    *, tmp_path: Path
) -> None:
    """The quota report and the rotation decision ignore what the reset read returned."""
    outcomes: list[tuple[int, list[str]]] = []
    for index, live_resets in enumerate(
        (
            {},
            {"anthropic-0": ResetReading(resets=(RECURRING,))},
            {
                "anthropic-0": None,
                "anthropic-1": ResetReading(resets=(), unreadable_reason="client surface"),
            },
        )
    ):
        harness = harness_with(home=tmp_path / str(index), live_resets=live_resets)
        code, _ = harness.run()
        outcomes.append((code, harness.switches))

    assert outcomes[0][1] == ["anthropic-1"], "the baseline pass did not rotate"
    assert outcomes[1] == outcomes[0]
    assert outcomes[2] == outcomes[0]


def test_a_reading_the_provider_declines_is_recorded_unreadable_not_empty(
    *, tmp_path: Path
) -> None:
    """A declined or failed read leaves a row marked unreadable; an empty read does not."""
    module_path = Path(__file__).resolve().parents[2] / "overseer" / "caam_pass_resets.py"
    assert module_path.is_file()
    module = importlib.import_module("caam_pass_resets")

    declined = ResetReading(resets=(), unreadable_reason="client surface is ineligible")
    readings: dict[str, tuple[ResetReading | None, str | None]] = {
        "declined": (declined, None),
        "failed": (None, "HTTP 500"),
        "silent": (None, None),
        "empty": (ResetReading(resets=()), None),
        "recurring": (ResetReading(resets=(RECURRING,)), None),
    }

    def source(*, creds_path: Path, now: float | None = None):
        del now
        return readings[creds_path.parent.name]

    profiles = tuple(ProfileUsage(name=name, source="live", usage=None) for name in readings)
    observed = {
        row.name: row.reset_reading
        for row in module.observe_pass_resets(
            active_name="not-a-profile", home=tmp_path, now=0.0, profiles=profiles, source=source
        )
    }

    assert observed["declined"] == declined
    assert observed["failed"] == ResetReading(resets=(), unreadable_reason="HTTP 500")
    assert observed["silent"] == ResetReading(resets=(), unreadable_reason="reset reading failed")
    assert observed["empty"] is not None and observed["empty"].unreadable_reason is None
    assert observed["recurring"] == ResetReading(resets=(RECURRING,))


def test_scenario_the_account_table_shows_each_accounts_resets(*, tmp_path: Path) -> None:
    """Two available reset uses render once, with the earliest lapse rounded down.

    This drives the shipped pass because the account table is its operator-facing
    report.  The two resets deliberately lapse at different times: counting reset
    records rather than their remaining uses, or selecting the later lapse, cannot
    satisfy the row assertion.
    """
    resets = (
        QuotaReset(
            program="cedar_ember",
            reset_id="first",
            clears=("five_hour",),
            uses_left=1,
            uses_total=1,
            lapses_at=reset_at(seconds_from_now=5 * 86_400 + 4 * 3_600 + 59 * 60),
            usable_now=True,
            requires_limit=False,
        ),
        QuotaReset(
            program="juniper_tide",
            reset_id="second",
            clears=("seven_day",),
            uses_left=1,
            uses_total=1,
            lapses_at=reset_at(seconds_from_now=8 * 86_400),
            usable_now=True,
            requires_limit=False,
        ),
    )
    harness = harness_with(
        home=tmp_path,
        live_resets={"anthropic-0": ResetReading(resets=resets)},
    )

    code, lines = harness.run()

    assert code == 0
    header = next(line for line in lines if line.startswith("PROFILE"))
    row = next(line for line in lines if line.startswith("anthropic-0"))
    assert "QUOTA RESETS" in header
    assert "2, next expires in 5d 4h" in row


def test_scenario_a_reset_reading_declined_for_the_requesting_client_is_unreadable_not_empty(
    *, tmp_path: Path
) -> None:
    """A declined pass read renders `unreadable`, not the empty-reading `0`."""
    harness = harness_with(
        home=tmp_path,
        live_resets={
            "anthropic-0": ResetReading(resets=(), unreadable_reason="client surface is ineligible")
        },
    )

    code, lines = harness.run()

    assert code == 0
    header = next(line for line in lines if line.startswith("PROFILE"))
    row = next(line for line in lines if line.startswith("anthropic-0"))
    quota_start = _terminal_column(line=header, text="QUOTA RESETS")
    assert _terminal_column(line=row, text="unreadable") == quota_start
    assert "unreadable" in _field(line=row, start=quota_start, width=28)


def test_a_reset_with_no_lapse_contributes_uses_but_not_a_next_expiry() -> None:
    cell = caam_rendering.quota_resets_cell(
        reading=ResetReading(resets=(RECURRING,)),
        now=datetime.fromtimestamp(NOW, tz=timezone.utc),
    )

    assert cell == "1"


def test_scenario_the_account_tables_columns_align_on_every_kind_of_row() -> None:
    """The table's fixed-width cells stay aligned across every row shape."""
    now = datetime.fromtimestamp(NOW, tz=timezone.utc)
    readable = ProfileUsage(
        name="readable",
        source="live",
        usage=UsageRecord(
            five_hour_remaining=81.0,
            seven_day_remaining=73.0,
            five_hour_resets_at=reset_at(seconds_from_now=2 * 3_600 + 30 * 60),
            seven_day_resets_at=reset_at(seconds_from_now=2 * 86_400 + 3 * 3_600 + 12 * 60),
            fable_remaining=59.0,
            fable_resets_at=reset_at(seconds_from_now=86_400 + 5 * 60),
            unrecognised_limits=(("other", 64.0, reset_at(seconds_from_now=2 * 3_600)),),
        ),
        reset_reading=ResetReading(resets=()),
    )
    rows = (
        ProfileUsage(
            name="active",
            source="live",
            usage=readable.usage,
            reset_reading=ResetReading(
                resets=(
                    QuotaReset(
                        program="cedar_ember",
                        reset_id="available",
                        clears=("five_hour",),
                        uses_left=2,
                        uses_total=2,
                        lapses_at=reset_at(seconds_from_now=5 * 86_400 + 4 * 3_600),
                        usable_now=True,
                        requires_limit=False,
                    ),
                )
            ),
        ),
        readable,
        ProfileUsage(
            name="no-short",
            source="live",
            usage=UsageRecord(
                five_hour_remaining=0.0,
                seven_day_remaining=73.0,
                five_hour_resets_at=None,
                seven_day_resets_at=reset_at(seconds_from_now=2 * 86_400),
                fable_remaining=59.0,
                fable_resets_at=reset_at(seconds_from_now=86_400),
                short_window_present=False,
                unrecognised_limits=(),
            ),
            reset_reading=ResetReading(resets=()),
        ),
        ProfileUsage(name="no-usage", source="dark: no token", usage=None),
        ProfileUsage(
            name="stale",
            source="cached 1.0h",
            usage=UsageRecord(
                five_hour_remaining=81.0,
                seven_day_remaining=73.0,
                five_hour_resets_at=reset_at(seconds_from_now=-60),
                seven_day_resets_at=reset_at(seconds_from_now=2 * 86_400),
                fable_remaining=59.0,
                fable_resets_at=reset_at(seconds_from_now=86_400),
            ),
        ),
    )

    header, *rendered = caam_rendering.render_table(
        rows=rows, active_name="active", now=now
    ).splitlines()[1:]
    columns = (
        ("PROFILE", 13, "left", 1),
        ("CURRENT", 8, "left", 1),
        ("5H LEFT", 7, "right", 1),
        ("5H RESET", 13, "right", 1),
        ("WEEK LEFT", 9, "right", 1),
        ("WEEK RESET", 13, "right", 1),
        ("FABLE LEFT", 10, "right", 1),
        ("FABLE RESET", 13, "right", 1),
        ("OTHER LIMITS", 29, "left", 1),
        ("QUOTA RESETS", 28, "left", 1),
        ("EXTRA", 7, "right", 1),
        ("$ LEFT", 8, "right", 2),
        ("CAPACITY", 30, "left", 2),
    )
    start = 0
    for title, width, alignment, spacing in columns:
        assert _field(line=header, start=start, width=width).strip() == title
        for line in rendered:
            field = _field(line=line, start=start, width=width)
            value = field.strip()
            if value:
                assert field.startswith(value) if alignment == "left" else field.endswith(value), (
                    title,
                    repr(field),
                    repr(value),
                    repr(line),
                )
        start += width + spacing
    assert _field(line=rendered[0], start=0, width=13).strip() == "active"
    assert _field(line=rendered[0], start=14, width=8).startswith("✅")
    assert _field(line=rendered[0], start=124, width=28).strip() == "2, next expires in 5d 4h"
    assert _field(line=rendered[1], start=124, width=28).strip() == "0"
    assert _field(line=rendered[2], start=124, width=28).strip() == "0"
    assert _field(line=rendered[3], start=124, width=28).strip() == "-"
    assert _field(line=rendered[4], start=124, width=28).strip() == "?"
    five_hour_start, five_hour_width = 23, 7
    reset_end = five_hour_start + five_hour_width + 1 + 13
    no_short_window = _field(
        line=rendered[2], start=five_hour_start, width=reset_end - five_hour_start
    ).strip()
    assert no_short_window == "no short-window limit"


def _terminal_column(*, line: str, text: str) -> int:
    return _terminal_width(text=line[: line.index(text)])


def _field(*, line: str, start: int, width: int) -> str:
    output = ""
    column = 0
    for character in line:
        character_width = 2 if character == "✅" else 1
        if start <= column and column + character_width <= start + width:
            output += character
        column += character_width
    return output


def _terminal_width(*, text: str) -> int:
    return sum(2 if character == "✅" else 1 for character in text)
