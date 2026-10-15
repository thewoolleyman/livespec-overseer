"""Integration-tier scenarios for capacity-class reporting (SPECIFICATION v056).

The three capacity-reporting scenarios of `SPECIFICATION/scenarios.md` are
driven through the SHIPPED rotation pass, exactly as the expiring-quota drain's
and the refusal trigger's scenarios are: nothing in the rendering path is
stubbed, so these fail if the column has no production caller.

Two things are injected, both of which production reads from the provider -- the
usage figures, and the live plan read. The plan read is injected BESIDE the usage
fetcher rather than inside it, because the specification makes them two separate
read-only requests sharing one credential, and a scenario in which the plan read
fails while the usage read succeeds (and the reverse) is only expressible when
they are separate seams.

WHAT MAKES THE SECOND SCENARIO A REAL TEST. The stored login-time credential is
written with the plan fields a real vault snapshot carries -- measured on host hp
2026-10-13, an account downgraded from $200 to $20 went on reporting
`subscriptionType: max` / `rateLimitTier: default_claude_max_20x` in its snapshot
because those fields are written at login and never again. The harness writes
exactly that disagreement, so an implementation that read the snapshot would
render `large` and fail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord
from caam_switch import SwitchRequest, SwitchResult

__all__: list[str] = []

pytestmark = pytest.mark.integration

NOW = 1_800_000_000.0
LARGE_PLAN = "default_claude_max_20x"
MEDIUM_PLAN = "default_claude_max_5x"
SMALL_PLAN = "default_claude_ai"
CAPACITY_CLASSES = ("small", "medium", "large", "unknown")


def reset_at(*, seconds_from_now: float) -> str:
    return (
        datetime.fromtimestamp(NOW + seconds_from_now, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def usage(*, five_hour_remaining: float = 80.0, seven_day_remaining: float = 80.0) -> UsageRecord:
    """A healthy account, with every window resetting at the same moment.

    Identical resets across the vault are deliberate: no candidate's weekly
    window resets sooner than the active account's, so the expiring-quota drain
    cannot fire and the pass holds. These scenarios are about what the table
    SAYS, so a rotation would only add a second table to read around.
    """
    return UsageRecord(
        five_hour_remaining=five_hour_remaining,
        seven_day_remaining=seven_day_remaining,
        five_hour_resets_at=reset_at(seconds_from_now=3_600.0),
        seven_day_resets_at=reset_at(seconds_from_now=604_800.0),
        fable_remaining=80.0,
        fable_resets_at=reset_at(seconds_from_now=604_800.0),
    )


@dataclass(kw_only=True)
class CapacityHarness:
    """One vault, with a stored plan and a live plan declared per account."""

    home: Path
    active: str
    usages: dict[str, UsageRecord]
    # The plan the provider answers the live read with, or None where that read
    # fails. Absent entirely means the account is not declared at all, which is
    # a third thing again and reads as a failed read.
    live_plans: dict[str, str | None] = field(default_factory=dict)
    stored_plans: dict[str, str] = field(default_factory=dict)
    failed_usage: set[str] = field(default_factory=set)
    plan_reads: list[Path] = field(default_factory=list)
    switches: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in self.usages:
            profile = self.home / ".local/share/caam/vault/claude" / name
            profile.mkdir(parents=True)
            self._write_snapshot(path=profile / ".credentials.json", name=name)
            self._write_account(path=profile / ".claude.json", name=name)
        self._write_account(path=self.home / ".claude.json", name=self.active)
        self._write_snapshot(path=self.home / ".claude/.credentials.json", name=self.active)

    def stored_snapshot(self, *, name: str) -> dict[str, object]:
        """What that account's stored credential says, as written at login time."""
        path = self.home / ".local/share/caam/vault/claude" / name / ".credentials.json"
        body: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        oauth = body["claudeAiOauth"]
        assert isinstance(oauth, dict)
        return oauth

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
            switch_account=self.switch_account,
            save_state=lambda *, state, state_path: None,
            enforce_models=lambda **kwargs: [],
        )
        return code, tuple(lines)

    def run_caam(self, *, args: tuple[str, ...]) -> object:
        del args
        body = json.dumps({"tools": [{"tool": "claude", "active_profile": self.active}]})
        return type("Process", (), {"returncode": 0, "stdout": body, "stderr": ""})()

    def fetch_usage(
        self, *, creds_path: Path, now: float | None = None
    ) -> tuple[UsageRecord | None, str | None]:
        del now
        name = self._account_of(creds_path=creds_path)
        if name in self.failed_usage:
            return None, "HTTP 429"
        return self.usages[name], None

    def read_plan(
        self, *, creds_path: Path, now: float | None = None
    ) -> tuple[str | None, str | None]:
        del now
        self.plan_reads.append(creds_path)
        plan = self.live_plans.get(self._account_of(creds_path=creds_path))
        if plan is None:
            return None, "HTTP 500"
        return plan, None

    def switch_account(self, *, request: SwitchRequest) -> SwitchResult:
        self.switches.append(request.target.name)
        return SwitchResult(exit_code=0, reason="switched", switched=True, lines=())

    def _account_of(self, *, creds_path: Path) -> str:
        if creds_path == self.home / ".claude/.credentials.json":
            return self.active
        return creds_path.parent.name

    def _write_account(self, *, path: Path, name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"oauthAccount": {"accountUuid": f"uuid-{name}"}}), encoding="utf-8"
        )

    def _write_snapshot(self, *, path: Path, name: str) -> None:
        """The account's credential, carrying the plan fields a LOGIN wrote.

        `subscriptionType` and `rateLimitTier` are exactly the fields the
        operation must not derive a class from, so they are present here on
        every account rather than only on the one scenario that contradicts
        them.
        """
        stored = self.stored_plans.get(name, LARGE_PLAN)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "claudeAiOauth": {
                        "accessToken": f"token-{name}",
                        "expiresAt": int((NOW + 86_400.0) * 1000),
                        "subscriptionType": "max" if stored == LARGE_PLAN else "pro",
                        "rateLimitTier": stored,
                    }
                }
            ),
            encoding="utf-8",
        )


def account_rows(*, lines: tuple[str, ...]) -> dict[str, str]:
    """Every data row of the rendered table, keyed by the account it names."""
    header = next(index for index, line in enumerate(lines) if line.startswith("PROFILE"))
    rows: dict[str, str] = {}
    for line in lines[header + 1 :]:
        if not line.strip():
            break
        rows[line.split()[0]] = line
    return rows


def capacity_of_row(*, row: str) -> str:
    """The capacity cell of one row: its class, and its plan-name detail if any."""
    found = [token for token in CAPACITY_CLASSES if f" {token}" in row]
    assert len(found) == 1, f"expected exactly one capacity class in {row!r}, got {found}"
    detail = row.split(f"{found[0]} (", 1)
    if len(detail) == 1:
        return found[0]
    return f"{found[0]} ({detail[1].split(')', 1)[0]})"


def test_scenario_the_account_table_shows_each_accounts_capacity_class(*, tmp_path: Path) -> None:
    """Given the provider reports a large plan for one account and a small plan for another,
    when the operation renders the account table, then each row shows its capacity
    class with the provider's plan name as detail.

    The third account is DARK -- its usage read fails -- and it is here because
    the requirement is every account ROW, not every readable one. The two reads
    are independent, so an account whose quota cannot be read can still have a
    perfectly readable plan, and its row must say so.
    """
    harness = CapacityHarness(
        home=tmp_path,
        active="anthropic-0",
        usages={
            "anthropic-0": usage(),
            "anthropic-3": usage(),
            "anthropic-4": usage(),
        },
        live_plans={
            "anthropic-0": LARGE_PLAN,
            "anthropic-3": SMALL_PLAN,
            "anthropic-4": MEDIUM_PLAN,
        },
        failed_usage={"anthropic-4"},
    )

    code, lines = harness.run()

    assert code == 0
    assert any("CAPACITY" in line for line in lines), "the table has no capacity column"
    rows = account_rows(lines=lines)
    assert sorted(rows) == ["anthropic-0", "anthropic-3", "anthropic-4"]
    assert capacity_of_row(row=rows["anthropic-0"]) == f"large ({LARGE_PLAN})"
    assert capacity_of_row(row=rows["anthropic-3"]) == f"small ({SMALL_PLAN})"
    assert capacity_of_row(row=rows["anthropic-4"]) == f"medium ({MEDIUM_PLAN})"


def test_scenario_a_plan_change_shows_without_a_fresh_login(*, tmp_path: Path) -> None:
    """Given an account's stored login-time credential names a large plan, and the
    provider's live read reports a small plan for that account, when the operation
    renders the account table, then that account's row shows the small capacity
    class.

    The stored field is asserted to BE there first. Without that control the test
    would pass against a build that read no plan source at all and happened to
    render `small` for another reason.
    """
    harness = CapacityHarness(
        home=tmp_path,
        active="anthropic-0",
        usages={"anthropic-0": usage(), "anthropic-2": usage()},
        live_plans={"anthropic-0": LARGE_PLAN, "anthropic-2": SMALL_PLAN},
        stored_plans={"anthropic-2": LARGE_PLAN},
    )

    stored = harness.stored_snapshot(name="anthropic-2")
    assert stored["rateLimitTier"] == LARGE_PLAN
    assert stored["subscriptionType"] == "max"

    code, lines = harness.run()

    assert code == 0
    assert capacity_of_row(row=account_rows(lines=lines)["anthropic-2"]) == f"small ({SMALL_PLAN})"


def test_scenario_an_unreadable_plan_shows_unknown(*, tmp_path: Path) -> None:
    """Given the live plan read for an account fails, when the operation renders the
    account table, then that account's row shows an unknown capacity class, and the
    pass does not fail on that account.

    The account whose plan DID read is the control: an implementation that
    reported `unknown` for everything would satisfy the first assertion and fail
    the second.
    """
    harness = CapacityHarness(
        home=tmp_path,
        active="anthropic-0",
        usages={"anthropic-0": usage(), "anthropic-1": usage()},
        live_plans={"anthropic-0": LARGE_PLAN, "anthropic-1": None},
        stored_plans={"anthropic-1": LARGE_PLAN},
    )

    code, lines = harness.run()

    assert code == 0, "an unknown capacity class must not on its own fail the pass"
    rows = account_rows(lines=lines)
    assert capacity_of_row(row=rows["anthropic-1"]) == "unknown"
    assert capacity_of_row(row=rows["anthropic-0"]) == f"large ({LARGE_PLAN})"


def test_the_plan_is_read_with_the_same_credential_the_usage_read_uses(*, tmp_path: Path) -> None:
    """The plan read uses the same credential the pass uses for that account's usage.

    The active account is polled through the HOST's live credential and every
    other account through its own stored snapshot. A capacity read that reached
    for the live credential every time would report the active account's plan for
    the whole vault -- which on a mixed-plan host is wrong for every row but one,
    and wrong in the direction that reads plausible.
    """
    harness = CapacityHarness(
        home=tmp_path,
        active="anthropic-0",
        usages={"anthropic-0": usage(), "anthropic-1": usage()},
        live_plans={"anthropic-0": LARGE_PLAN, "anthropic-1": SMALL_PLAN},
    )

    code, _ = harness.run()

    assert code == 0
    assert sorted(harness.plan_reads) == [
        tmp_path / ".claude/.credentials.json",
        tmp_path / ".local/share/caam/vault/claude/anthropic-1/.credentials.json",
    ]
