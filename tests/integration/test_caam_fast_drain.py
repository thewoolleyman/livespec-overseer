"""Integration-tier scenarios for the fast-drain trigger (SPECIFICATION v056).

The fast-drain scenarios of `SPECIFICATION/scenarios.md` are driven through the
SHIPPED rotation pass, exactly as the expiring-quota drain's and the refusal
trigger's scenarios are. Nothing in the decision path is stubbed: a scenario
states what the provider answered on each pass and the instant that pass ran,
and the operation's own durable store carries everything else between them.

PASSES RUN AT CONTROLLED CLOCK OFFSETS, and that is the whole point of this
tier here. A burn rate is a measurement ACROSS two readings, so no single-pass
fixture can express one -- the baseline reading, the activation time and the
fleet load all live in the durable store between passes, and two passes sharing
one clock would measure a fall of zero over an elapsed time of zero.

Three things are injected, all of which production reads from the provider or
the host: the usage figures, the live plan read each account's capacity class
comes from, and the account manager's own switch. `RotationHarness` is shared
with `test_caam_capacity_test`, which drives the capacity-test half of the same
ratified clause.
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
from caam_profile_state import STATE_REL
from caam_switch import REASON_SWITCHED, SwitchRequest, SwitchResult

__all__: list[str] = []

pytestmark = pytest.mark.integration

NOW = 1_800_000_000.0
# The documented interval of this operation's own schedule, which is also the
# documented default of the projection horizon the fast-drain trigger projects
# across. A scenario that spans several passes spans them the way the fleet does.
PASS_INTERVAL = 1_800.0
LARGE_PLAN = "default_claude_max_20x"
MEDIUM_PLAN = "default_claude_max_5x"
SMALL_PLAN = "default_claude_ai"


def reset_at(*, seconds_from_now: float) -> str:
    return (
        datetime.fromtimestamp(NOW + seconds_from_now, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def usage(
    *,
    five_hour_remaining: float = 80.0,
    seven_day_remaining: float = 80.0,
    five_hour_reset_s: float | None = 3_600.0,
    seven_day_reset_s: float | None = 604_800.0,
    fable_remaining: float | None = 80.0,
) -> UsageRecord:
    """One account's reading, with every reset stated against the SAME instant.

    The short-window reset is anchored on `NOW` rather than on the pass's own
    clock deliberately: two readings of one short window report the same reset,
    and a helper that moved the reset with the pass would straddle a window on
    every scenario that spans two passes.
    """
    return UsageRecord(
        five_hour_remaining=five_hour_remaining,
        seven_day_remaining=seven_day_remaining,
        five_hour_resets_at=(
            None if five_hour_reset_s is None else reset_at(seconds_from_now=five_hour_reset_s)
        ),
        seven_day_resets_at=(
            None if seven_day_reset_s is None else reset_at(seconds_from_now=seven_day_reset_s)
        ),
        fable_remaining=fable_remaining,
        fable_resets_at=reset_at(seconds_from_now=604_800.0),
    )


@dataclass(kw_only=True)
class RotationHarness:
    """One vault, polled across as many passes as a scenario needs.

    `usages` and `live_plans` are what the provider ANSWERS, and a scenario
    rewrites them between passes through `read` -- which is how a fall in
    remaining across one projection horizon is expressed.
    """

    home: Path
    active: str
    usages: dict[str, UsageRecord]
    # The plan the provider answers the live read with, or None where that read
    # fails. An account absent from this mapping reads as a failed read, which
    # is the shape an unknown capacity class arrives in.
    live_plans: dict[str, str | None] = field(default_factory=dict)
    failed_profiles: set[str] = field(default_factory=set)
    switches: list[str] = field(default_factory=list)
    plan_reads: list[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in self.usages:
            profile = self.home / ".local/share/caam/vault/claude" / name
            profile.mkdir(parents=True)
            (profile / ".credentials.json").write_text("{}\n", encoding="utf-8")
            self._write_account(path=profile / ".claude.json", name=name)
        self._write_account(path=self.home / ".claude.json", name=self.active)

    def read(self, *, name: str, record: UsageRecord) -> None:
        """What the provider answers for one account from the next pass on."""
        self.usages[name] = record

    def hand_switch(self, *, to: str) -> None:
        """The operator switching the host off an account themselves.

        The operation is told nothing: it observes the new active account on its
        next pass exactly as it observes its own switches.
        """
        self.active = to
        self._write_account(path=self.home / ".claude.json", name=to)

    def seed_state(self, *, state: dict[str, object]) -> None:
        path = self.home / STATE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")

    def read_state(self) -> dict[str, object]:
        return json.loads((self.home / STATE_REL).read_text(encoding="utf-8"))

    def remember_refusal(
        self, *, account: str, recorded_at: float, resets_at_epoch: float, window: str = "five_hour"
    ) -> None:
        """Append one attributed refusal to the operation's own durable store.

        A refusal is attributed from a tracked session's transcript on an
        earlier pass, and what the decision reads is this record. Writing the
        record is what lets a capacity-test scenario state "the active account
        is refusing" without also restating the attribution rules, which
        `test_caam_refusal_trigger` already drives end to end.
        """
        state = self.read_state()
        remembered = state.get("refusals")
        rows = list(remembered) if isinstance(remembered, list) else []
        rows.append(
            {
                "account": account,
                "window": window,
                "recorded_at": recorded_at,
                "resets_at": resets_at_epoch,
                "window_reset_at": resets_at_epoch,
                "identity": None,
            }
        )
        state["refusals"] = rows
        self.seed_state(state=state)

    def run(
        self,
        *,
        at: float = NOW,
        scheduled: bool = True,
        force: bool = False,
        protected_accounts: tuple[tuple[str, str], ...] = (),
    ) -> tuple[int, tuple[str, ...]]:
        lines: list[str] = []
        code = run_pass(
            flags=Flags(
                scheduled=scheduled,
                force=force,
                dry_run=False,
                no_models=True,
                no_warm=True,
                session_models=(),
                protected_accounts=protected_accounts,
            ),
            home=self.home,
            now=at,
            stdout=lines.append,
            caam_runner=self.run_caam,
            fetcher=self.fetch_usage,
            capacity_source=self.read_plan,
            switch_account=self.switch_account,
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
        if name in self.failed_profiles:
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
        target = request.target.name
        self.switches.append(target)
        request.state["last_switch"] = {
            "at": request.now,
            "from": request.active_name,
            "to": target,
        }
        request.save(state=request.state)
        self.hand_switch(to=target)
        return SwitchResult(
            exit_code=0,
            reason=REASON_SWITCHED,
            switched=True,
            lines=(f"SWITCHED {request.active_name} -> {target}",),
        )

    def _account_of(self, *, creds_path: Path) -> str:
        if creds_path == self.home / ".claude/.credentials.json":
            return self.active
        return creds_path.parent.name

    def _write_account(self, *, path: Path, name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"oauthAccount": {"accountUuid": f"uuid-{name}"}}),
            encoding="utf-8",
        )


def test_scenario_an_account_projected_to_reach_the_floor_before_the_next_pass_is_left(
    *, tmp_path: Path
) -> None:
    """Given the active account's short-window remaining fell from 75% to 36% between a
    baseline and a reading of the same window one projection horizon apart, and the
    short-window floor is 15% remaining, and an eligible candidate exists, when a
    scheduled pass runs, then the operation rotates off the active account.

    The FIRST pass is what makes this a measurement rather than a fixture: it
    reads 75%, records the baseline and holds, because nothing a single reading
    carries can say how fast an account is falling. The second pass reads 36% one
    projection horizon later, which is a fall of 39 points per horizon against a
    36-point margin -- so the account reaches the floor before the pass after
    this one, while every percentage the other triggers read is still healthy.

    The hold on the first pass is the control. Without it a build that rotated
    on the 36% reading alone -- on no burn rate at all -- would pass.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="draining",
        usages={
            "draining": usage(five_hour_remaining=75.0),
            "spare": usage(five_hour_remaining=90.0),
        },
        live_plans={"draining": LARGE_PLAN, "spare": LARGE_PLAN},
    )

    first_code, first_lines = harness.run(at=NOW)
    harness.read(name="draining", record=usage(five_hour_remaining=36.0))
    second_code, _second_lines = harness.run(at=NOW + PASS_INTERVAL)

    assert first_code == second_code == 0
    assert any(line.startswith("hold:") for line in first_lines)
    assert harness.switches == ["spare"]
