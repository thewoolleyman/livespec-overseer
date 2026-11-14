"""Integration-tier reset observation through the shipped rotation pass.

The pass reads each managed account's quota resets alongside its quota poll. The
reading is observation only: whatever it returns, fails or declines, the quota
report and the rotation decision stay exactly what they would have been without it.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import ProfileUsage, UsageRecord
from caam_resets import QuotaReset, ResetReading

from tests.integration.test_caam_capacity_reporting import (
    LARGE_PLAN,
    NOW,
    CapacityHarness,
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
    outcomes: list[tuple[int, tuple[str, ...], list[str]]] = []
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
        code, lines = harness.run()
        outcomes.append((code, lines, harness.switches))

    assert outcomes[0][2] == ["anthropic-1"], "the baseline pass did not rotate"
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
