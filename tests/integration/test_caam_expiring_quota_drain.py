"""Integration-tier scenarios for draining expiring weekly quota."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import ProfileUsage, UsageRecord, rank_profiles
from caam_profile_state import STATE_REL
from caam_switch import REASON_SWITCHED, SwitchRequest, SwitchResult

__all__: list[str] = []

pytestmark = pytest.mark.integration

NOW = 1_800_000_000.0


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
    home: Path
    active: str
    usages: dict[str, UsageRecord]
    failed_profiles: set[str] = field(default_factory=set)
    switches: list[str] = field(default_factory=list)
    fetches: list[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in self.usages:
            profile = self.home / ".local/share/caam/vault/claude" / name
            profile.mkdir(parents=True)
            (profile / ".credentials.json").write_text("{}\n", encoding="utf-8")
            self._write_account(path=profile / ".claude.json", name=name)
        self._write_account(path=self.home / ".claude.json", name=self.active)

    def seed_state(self, *, state: dict[str, object]) -> None:
        path = self.home / STATE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")

    def read_state(self) -> dict[str, object]:
        return json.loads((self.home / STATE_REL).read_text(encoding="utf-8"))

    def run(
        self,
        *,
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
            now=NOW,
            stdout=lines.append,
            caam_runner=self.run_caam,
            fetcher=self.fetch_usage,
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
        self.fetches.append(creds_path)
        name = (
            self.active
            if creds_path == self.home / ".claude/.credentials.json"
            else creds_path.parent.name
        )
        if name in self.failed_profiles:
            return None, "HTTP 429"
        return self.usages[name], None

    def switch_account(self, *, request: SwitchRequest) -> SwitchResult:
        target = request.target.name
        self.switches.append(target)
        request.state["last_switch"] = {
            "at": request.now,
            "from": request.active_name,
            "to": target,
        }
        request.save(state=request.state)
        self.active = target
        self._write_account(path=self.home / ".claude.json", name=target)
        return SwitchResult(
            exit_code=0,
            reason=REASON_SWITCHED,
            switched=True,
            lines=(f"SWITCHED {request.active_name} -> {target}",),
        )

    @staticmethod
    def profile(*, name: str, record: UsageRecord) -> ProfileUsage:
        return ProfileUsage(name=name, source="live", usage=record)

    def _write_account(self, *, path: Path, name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"oauthAccount": {"accountUuid": f"uuid-{name}"}}),
            encoding="utf-8",
        )


def test_scenario_a_scheduled_pass_drains_weekly_quota_that_resets_sooner(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "drain": usage(seven_day_remaining=70.0, seven_day_reset_s=86_400.0),
        },
    )

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == ["drain"]
    assert tmp_path / ".local/share/caam/vault/claude/drain/.credentials.json" in harness.fetches
    switched = next(line for line in lines if line.startswith("SWITCHED"))
    assert "expiring weekly quota" in switched
    assert "70%" in switched
    assert "resets in 1d 0h 0m" in switched


def test_scenario_a_scheduled_pass_holds_when_no_candidates_weekly_window_resets_sooner(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=86_400.0),
            "later": usage(seven_day_reset_s=172_800.0),
        },
    )

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == []
    assert any(line.startswith("hold:") for line in lines)


def test_scenario_a_drain_rotation_does_not_reverse_on_the_next_pass(*, tmp_path: Path) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="later",
        usages={
            "later": usage(seven_day_reset_s=604_800.0),
            "sooner": usage(seven_day_reset_s=86_400.0),
        },
    )

    first_code, _first_lines = harness.run()
    second_code, second_lines = harness.run()

    assert first_code == second_code == 0
    assert harness.switches == ["sooner"]
    assert any(line.startswith("hold:") for line in second_lines)


def test_scenario_two_accounts_sharing_a_nominal_weekly_reset_do_not_drain_onto_each_other(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="first",
        usages={
            "first": usage(seven_day_reset_s=86_420.0),
            "second": usage(seven_day_reset_s=86_380.0),
        },
    )

    first_code, _first_lines = harness.run()
    second_code, _second_lines = harness.run()

    assert first_code == second_code == 0
    assert harness.switches == []


def test_scenario_an_unreadable_active_weekly_reset_prevents_a_drain(*, tmp_path: Path) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=None),
            "candidate": usage(seven_day_reset_s=86_400.0),
        },
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []


def test_scenario_a_candidate_whose_weekly_reset_cannot_be_read_does_not_attract_a_drain(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=604_800.0),
            "candidate": usage(seven_day_reset_s=None),
        },
    )

    code, _lines = harness.run()

    assert code == 0
    assert harness.switches == []


def test_scenario_another_trigger_on_the_same_pass_governs_instead_of_the_drain(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=15.0, seven_day_reset_s=604_800.0),
            "candidate": usage(five_hour_remaining=20.0, seven_day_reset_s=86_400.0),
        },
    )

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == []
    assert any("comparing candidates on five_hour" in line for line in lines)
    assert all("expiring weekly quota" not in line for line in lines)


def test_scenario_ranking_ignores_plan_capacity(*, tmp_path: Path) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(seven_day_reset_s=777_600.0),
            "large-plan": usage(seven_day_reset_s=172_800.0),
            "small-plan": usage(seven_day_reset_s=86_400.0),
        },
    )
    ranked = rank_profiles(
        profiles=(
            harness.profile(name="large-plan", record=harness.usages["large-plan"]),
            harness.profile(name="small-plan", record=harness.usages["small-plan"]),
        )
    )

    code, _lines = harness.run()

    assert tuple(profile.name for profile in ranked) == ("small-plan", "large-plan")
    assert code == 0
    assert harness.switches == ["small-plan"]


def test_scenario_an_invocation_without_the_scheduled_marker_does_not_drain(
    *, tmp_path: Path
) -> None:
    harness = RotationHarness(
        home=tmp_path,
        active="active",
        usages={
            "active": usage(five_hour_remaining=80.0, seven_day_reset_s=604_800.0),
            "candidate": usage(five_hour_remaining=95.0, seven_day_reset_s=86_400.0),
        },
    )

    code, lines = harness.run(scheduled=False, force=True)

    assert code == 0
    assert harness.switches == ["candidate"]
    assert all("expiring weekly quota" not in line for line in lines)
    assert reset_at(seconds_from_now=86_400.0).startswith("2027-")
    assert NOW > 0
