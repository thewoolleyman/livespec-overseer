"""Integration-tier scenarios for the usage-limit refusal trigger (SPECIFICATION v056).

The refusal scenarios of `SPECIFICATION/scenarios.md` are driven through the
SHIPPED rotation pass, exactly as the expiring-quota drain's scenarios are: the
harness writes a real transcript under a real agent configuration directory and
lets `run_pass` find and parse it. Two things are injected, both of which
production discovers rather than computes -- the set of tracked sessions, which
production reads from tmux and `/proc`, and the usage figures, which production
reads from the provider.

A tracked session is injected as a STAND-IN carrying exactly the three facts the
operation reads of one: the transcript id, the agent configuration directory
whose credential that session authenticates with, and its provider. A scenario
then states those facts where a reader can see them, rather than through a
process tree the test would have to fake for no gain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import ProfileUsage, UsageRecord
from caam_profile_state import STATE_REL
from caam_switch import REASON_SWITCHED, SwitchRequest, SwitchResult

__all__: list[str] = []

pytestmark = pytest.mark.integration

NOW = 1_800_000_000.0
ONE_HOUR = 3_600.0
NINE_MINUTES = 540.0
# The documented interval of this operation's own schedule, so a scenario that
# spans several passes spans them the way the fleet does.
PASS_INTERVAL = 1_800.0


def reset_at(*, seconds_from_now: float) -> str:
    return (
        datetime.fromtimestamp(NOW + seconds_from_now, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def stamp(*, at: float) -> str:
    return datetime.fromtimestamp(at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def usage(
    *,
    five_hour_remaining: float = 80.0,
    seven_day_remaining: float = 80.0,
    five_hour_reset_s: float | None = ONE_HOUR,
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


@dataclass(frozen=True, kw_only=True)
class StandInSession:
    """The three facts the operation reads of a tracked session, and nothing else."""

    session_id: str
    config_dir: Path
    provider: str = "anthropic"


@dataclass(kw_only=True)
class RotationHarness:
    home: Path
    active: str
    usages: dict[str, UsageRecord]
    sessions: tuple[StandInSession, ...] = ()
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

    @property
    def live_config_dir(self) -> Path:
        """The host's default agent configuration directory -- the live credential's."""
        return self.home / ".claude"

    def record_refusal(
        self,
        *,
        session_id: str = "live-session",
        config_dir: Path | None = None,
        recorded_at: float,
        reset_at_epoch: float | None,
        weekly: bool = False,
    ) -> StandInSession:
        """Write one provider refusal record into a session's transcript.

        The epoch form of Anthropic's subscription-limit error, which is the one
        that states its own reset. `reset_at_epoch` of None writes the error with
        no reset at all, which is the shape the hold's replenishment rule governs.
        """
        directory = self.live_config_dir if config_dir is None else config_dir
        limit = "weekly limit" if weekly else "usage limit"
        suffix = "" if reset_at_epoch is None else f"|{int(reset_at_epoch)}"
        path = directory / "projects" / "-data-projects-livespec" / f"{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            _ = handle.write(
                json.dumps(
                    {
                        "type": "assistant",
                        "timestamp": stamp(at=recorded_at),
                        "isApiErrorMessage": True,
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": f"Claude AI {limit} reached{suffix}"}
                            ],
                        },
                    }
                )
                + "\n"
            )
        return StandInSession(session_id=session_id, config_dir=directory)

    def track(self, *, sessions: tuple[StandInSession, ...]) -> None:
        self.sessions = sessions

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

    def run(
        self,
        *,
        at: float = NOW,
        scheduled: bool = True,
        force: bool = False,
        protected_accounts: tuple[tuple[str, str], ...] = (),
    ) -> tuple[int, tuple[str, ...]]:
        """One pass, at its own instant.

        `at` is what lets a scenario span several passes the way the schedule
        does: the operation records when it OBSERVED an account become active,
        so a refusal recorded after a switch can only be told from one recorded
        before it when the passes do not share a clock.
        """
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
            switch_account=self.switch_account,
            enforce_models=lambda **kwargs: [],
            tracked_sessions=self.tracked_sessions,
        )
        return code, tuple(lines)

    def tracked_sessions(self, *, home: Path) -> tuple[StandInSession, ...]:
        assert home == self.home
        return self.sessions

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


def active_since(*, account: str, at: float) -> dict[str, object]:
    """The durable record of when an account was last observed to become active."""
    return {"active_since": {"account": account, "at": at}}


def test_scenario_a_refusing_active_account_is_left_whatever_its_usage_reads(
    *, tmp_path: Path
) -> None:
    """The measured 2026-10-13 incident, driven end to end.

    anthropic-3 read 45% five-hour remaining -- comfortably clear of the 15%
    floor -- while a tracked session on the live credential had already recorded
    a session-limit refusal nine minutes earlier. Every pass held. It must
    rotate.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=45.0),
            "anthropic-1": usage(five_hour_remaining=90.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    session = harness.record_refusal(recorded_at=NOW - NINE_MINUTES, reset_at_epoch=NOW + ONE_HOUR)
    harness.track(sessions=(session,))

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == ["anthropic-1"]
    assert any("usage-limit refusal" in line for line in lines)


def test_scenario_the_switch_line_names_the_refusal_and_when_it_was_recorded(
    *, tmp_path: Path
) -> None:
    """A move made under this trigger must be reported as such.

    The second half -- WHEN the refusal was recorded -- is the load-bearing one
    for an operator reading the log afterwards: the usage figures in the table
    beside it disagree with the decision, and that instant is what reconciles
    them.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=45.0),
            "anthropic-1": usage(five_hour_remaining=90.0, seven_day_remaining=70.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    session = harness.record_refusal(recorded_at=NOW - NINE_MINUTES, reset_at_epoch=NOW + ONE_HOUR)
    harness.track(sessions=(session,))

    _code, lines = harness.run()

    switched = next(line for line in lines if line.startswith("SWITCHED"))
    assert "usage-limit refusal" in switched
    assert "5-hour window" in switched
    assert stamp(at=NOW - NINE_MINUTES) in switched
    assert "70% week left" in switched


def test_scenario_the_operation_does_not_return_to_an_account_inside_its_refusal_window(
    *, tmp_path: Path
) -> None:
    """The lagging reading that would otherwise pull the fleet straight back.

    The account the first pass left is exactly the one whose usage figures still
    look healthiest, because those figures are what lagged in the first place.
    Without the hold the second pass reads 90% on it and returns -- which is the
    oscillation the trigger would otherwise introduce.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=45.0),
            "anthropic-1": usage(five_hour_remaining=90.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    session = harness.record_refusal(recorded_at=NOW - NINE_MINUTES, reset_at_epoch=NOW + ONE_HOUR)
    harness.track(sessions=(session,))

    first_code, _first_lines = harness.run()
    harness.usages["anthropic-1"] = usage(five_hour_remaining=10.0)
    harness.track(sessions=())
    second_code, second_lines = harness.run()

    assert first_code == second_code == 0
    assert harness.switches == ["anthropic-1"]
    assert any(line.startswith("hold:") for line in second_lines)


def test_scenario_reading_jitter_does_not_end_a_hold_on_a_refusal_with_no_reset(
    *, tmp_path: Path
) -> None:
    """A reset half a minute later is the provider's own jitter, not a reset."""
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=45.0, five_hour_reset_s=ONE_HOUR),
            "anthropic-1": usage(five_hour_remaining=90.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    session = harness.record_refusal(recorded_at=NOW - NINE_MINUTES, reset_at_epoch=None)
    harness.track(sessions=(session,))

    harness.run()
    harness.usages["anthropic-3"] = usage(
        five_hour_remaining=45.0, five_hour_reset_s=ONE_HOUR + 30.0
    )
    harness.usages["anthropic-1"] = usage(five_hour_remaining=10.0)
    harness.track(sessions=())
    _code, lines = harness.run()

    assert harness.switches == ["anthropic-1"]
    assert any(line.startswith("hold:") for line in lines)


def test_scenario_a_window_that_actually_reset_ends_the_hold_on_a_refusal_with_no_reset(
    *, tmp_path: Path
) -> None:
    """The control for the two holds above: a hold that could not END is not a hold.

    A refusal that reported no reset is held until the named window is OBSERVED
    to have moved on -- a reset more than the tolerance later, or a fully
    replenished reading -- and then the account is selectable again.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=45.0, five_hour_reset_s=ONE_HOUR),
            "anthropic-1": usage(five_hour_remaining=90.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    session = harness.record_refusal(recorded_at=NOW - NINE_MINUTES, reset_at_epoch=None)
    harness.track(sessions=(session,))

    harness.run()
    harness.usages["anthropic-3"] = usage(
        five_hour_remaining=100.0, five_hour_reset_s=ONE_HOUR + 6 * ONE_HOUR
    )
    harness.usages["anthropic-1"] = usage(five_hour_remaining=10.0)
    harness.track(sessions=())
    _code, _lines = harness.run()

    assert harness.switches == ["anthropic-1", "anthropic-3"]
    assert harness.read_state()["refusals"] == []


def test_scenario_a_refusal_from_another_credential_or_provider_is_not_attributed(
    *, tmp_path: Path
) -> None:
    """Three sessions that refused, none of them spending the live credential.

    The refresh-maintenance sandbox deliberately exercises OTHER accounts'
    stored credentials, so its refusals are about those accounts; a separately
    provisioned credential is somebody else's account entirely; and another
    provider's refusal says nothing about this one. The discriminator is the
    session's own agent configuration directory, read from the process that
    wrote the transcript.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(seven_day_reset_s=86_400.0),
            "anthropic-1": usage(five_hour_remaining=95.0, seven_day_reset_s=172_800.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    sandbox = harness.record_refusal(
        session_id="refresh-sandbox",
        config_dir=tmp_path / ".cache/caam-refresh/anthropic-1",
        recorded_at=NOW - NINE_MINUTES,
        reset_at_epoch=NOW + ONE_HOUR,
    )
    provisioned = harness.record_refusal(
        session_id="provisioned",
        config_dir=tmp_path / ".config/claude-provisioned",
        recorded_at=NOW - NINE_MINUTES,
        reset_at_epoch=NOW + ONE_HOUR,
    )
    foreign = harness.record_refusal(
        session_id="other-provider",
        recorded_at=NOW - NINE_MINUTES,
        reset_at_epoch=NOW + ONE_HOUR,
    )
    harness.track(
        sessions=(
            sandbox,
            provisioned,
            StandInSession(
                session_id=foreign.session_id,
                config_dir=foreign.config_dir,
                provider="openai",
            ),
        )
    )

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == []
    assert all("usage-limit refusal" not in line for line in lines)


def test_scenario_a_refusal_recorded_before_the_account_became_active_is_not_attributed(
    *, tmp_path: Path
) -> None:
    """It belongs to whatever was active then, which this account was not."""
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(seven_day_reset_s=86_400.0),
            "anthropic-1": usage(five_hour_remaining=95.0, seven_day_reset_s=172_800.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - ONE_HOUR))
    session = harness.record_refusal(
        recorded_at=NOW - ONE_HOUR - 60.0, reset_at_epoch=NOW + ONE_HOUR
    )
    harness.track(sessions=(session,))

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == []
    assert all("usage-limit refusal" not in line for line in lines)


def test_scenario_a_refusal_whose_reset_has_passed_does_not_trigger_rotation(
    *, tmp_path: Path
) -> None:
    """The window it named has already recovered, so it is not ground truth now."""
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(seven_day_reset_s=86_400.0),
            "anthropic-1": usage(five_hour_remaining=95.0, seven_day_reset_s=172_800.0),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))
    session = harness.record_refusal(recorded_at=NOW - NINE_MINUTES, reset_at_epoch=NOW - 60.0)
    harness.track(sessions=(session,))

    code, lines = harness.run()

    assert code == 0
    assert harness.switches == []
    assert all("usage-limit refusal" not in line for line in lines)


def test_scenario_a_lagging_refusal_after_a_switch_stays_with_the_account_just_left(
    *, tmp_path: Path
) -> None:
    """Concurrent sessions keep spending a departed credential for a while.

    Their refusals belong to the account just left, and the only thing that
    tells them apart from the new account's own is the reset they report
    matching the one that account was last read at.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=10.0, five_hour_reset_s=ONE_HOUR),
            "anthropic-1": usage(five_hour_remaining=95.0, five_hour_reset_s=3 * ONE_HOUR),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))

    harness.run(at=NOW)
    harness.run(at=NOW + PASS_INTERVAL)
    lagging = harness.record_refusal(
        session_id="lagging",
        recorded_at=NOW + PASS_INTERVAL + 60.0,
        reset_at_epoch=NOW + ONE_HOUR + 30.0,
    )
    harness.track(sessions=(lagging,))
    code, lines = harness.run(at=NOW + 2 * PASS_INTERVAL)

    assert code == 0
    assert harness.switches == ["anthropic-1"]
    assert all("usage-limit refusal" not in line for line in lines)


def test_scenario_a_lagging_refusal_after_a_hand_switch_stays_with_the_account_left(
    *, tmp_path: Path
) -> None:
    """The operation did not make this switch, and that changes nothing.

    It records an activation whenever it observes one, so the account the
    previous activation named is departed either way.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_reset_s=ONE_HOUR),
            "anthropic-1": usage(five_hour_remaining=95.0, five_hour_reset_s=3 * ONE_HOUR),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))

    harness.run(at=NOW)
    harness.hand_switch(to="anthropic-1")
    harness.run(at=NOW + PASS_INTERVAL)
    lagging = harness.record_refusal(
        session_id="lagging",
        recorded_at=NOW + PASS_INTERVAL + 60.0,
        reset_at_epoch=NOW + ONE_HOUR + 30.0,
    )
    harness.track(sessions=(lagging,))
    code, lines = harness.run(at=NOW + 2 * PASS_INTERVAL)

    assert code == 0
    assert harness.switches == []
    assert all("usage-limit refusal" not in line for line in lines)


def test_scenario_a_refusal_on_an_account_returned_to_is_attributed_to_it(
    *, tmp_path: Path
) -> None:
    """The other half of the departed rule: an account is never its own departure.

    An account returned to before its departed entry's resets passed must still
    be able to refuse on its OWN account, which is why the entry is dropped the
    moment that account becomes active again.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="anthropic-3",
        usages={
            "anthropic-3": usage(five_hour_remaining=10.0, five_hour_reset_s=4 * ONE_HOUR),
            "anthropic-1": usage(five_hour_remaining=95.0, five_hour_reset_s=6 * ONE_HOUR),
        },
    )
    harness.seed_state(state=active_since(account="anthropic-3", at=NOW - 2 * ONE_HOUR))

    harness.run(at=NOW)
    harness.run(at=NOW + PASS_INTERVAL)
    harness.hand_switch(to="anthropic-3")
    harness.usages["anthropic-3"] = usage(five_hour_remaining=45.0, five_hour_reset_s=4 * ONE_HOUR)
    harness.run(at=NOW + 2 * PASS_INTERVAL)
    own = harness.record_refusal(
        session_id="own",
        recorded_at=NOW + 2 * PASS_INTERVAL + 60.0,
        reset_at_epoch=NOW + 4 * ONE_HOUR,
    )
    harness.track(sessions=(own,))
    code, lines = harness.run(at=NOW + 3 * PASS_INTERVAL)

    assert code == 0
    assert harness.switches == ["anthropic-1", "anthropic-1"]
    assert any("usage-limit refusal" in line for line in lines)
