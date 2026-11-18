"""Integration coverage for factory-credential probe alerts.

These tests drive the shipped caam rotation pass (``caam_anthropic_pass.run_pass``)
through the five factory-credential alert scenarios in
``SPECIFICATION/scenarios.md``.  The probe list, the credential locations, the
durable alert conditions and the push channel are real files under a scratch
home; only the provider usage read and the HTTP post to the push channel are
injected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from caam_anthropic_loop import Flags
from caam_anthropic_pass import run_pass
from caam_decision import UsageRecord

__all__: list[str] = []

pytestmark = pytest.mark.integration

ACTIVE = "anthropic-4"
NOW = 1_795_000_000.0
HOUR = 3_600.0
PROBE_LIST_REL = Path(".config/caam-usage-rotate/factory-probe-list.json")
CONDITIONS_REL = Path(".local/state/caam-usage-rotate/factory-probe-conditions.json")
KEY = "tenant-a/factory-a"
Reply = tuple[UsageRecord | None, str | None]


@dataclass(frozen=True, kw_only=True)
class _CaamResult:
    returncode: int
    stdout: str
    stderr: str = ""


def _usage(*, weekly: float = 70.0, short: float = 80.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=short,
        seven_day_remaining=weekly,
        five_hour_resets_at="2026-11-17T12:00:00Z",
        seven_day_resets_at="2026-11-19T00:00:00Z",
        fable_remaining=90.0,
        fable_resets_at="2026-11-19T00:00:00Z",
    )


@dataclass(kw_only=True)
class _Pass:
    """One scratch home plus everything a rotation pass can be observed through."""

    root: Path
    reply: Reply = field(default_factory=lambda: (_usage(), None))
    probes: int = 0
    pushed: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    push_outcome: str = "sent 200"

    @property
    def location(self) -> Path:
        return self.root / "factory-a.credentials.json"

    def setup(self, *, channel: bool = True, readable: bool = True) -> _Pass:
        vault = self.root / ".local/share/caam/vault/claude" / ACTIVE
        vault.mkdir(parents=True)
        _ = (vault / ".claude.json").write_text(
            json.dumps({"oauthAccount": {"accountUuid": "uuid-active"}}), encoding="utf-8"
        )
        _ = (self.root / ".claude.json").write_text(
            json.dumps({"oauthAccount": {"accountUuid": "uuid-active"}}), encoding="utf-8"
        )
        if readable:
            _ = self.location.write_text("{}", encoding="utf-8")
        if channel:
            self.write(rel=Path(".claude/settings.json"), body={"env": {"CLAUDE_NTFY_TOPIC": "t"}})
        return self

    def write(self, *, rel: Path, body: object) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(json.dumps(body), encoding="utf-8")

    def probe_list(self, *, extra: dict[str, object] | None = None) -> _Pass:
        entry = {"label": "factory-a", "tenant": "tenant-a", "location": str(self.location)}
        self.write(rel=PROBE_LIST_REL, body={"credentials": [entry], **(extra or {})})
        return self

    def condition(self, *, alerted_ago: float) -> _Pass:
        stamp = {"started_at": NOW - alerted_ago, "alerted_at": NOW - alerted_ago}
        self.write(rel=CONDITIONS_REL, body={"conditions": {KEY: stamp}})
        return self

    def fetch(self, *, creds_path: Path, now: float | None = None) -> Reply:
        del now
        if creds_path != self.location:
            return _usage(), None
        self.probes += 1
        return self.reply

    def post(self, *, url: str, message: str) -> str:
        del url
        self.pushed.append(message)
        return self.push_outcome

    def run(self, *, dry_run: bool = False, at: float = NOW, scheduled: bool = True) -> int:
        flags = Flags(
            scheduled=scheduled,
            force=False,
            dry_run=dry_run,
            no_models=True,
            no_warm=True,
            session_models=(),
            protected_accounts=(),
        )
        return run_pass(
            flags=flags,
            home=self.root,
            now=at,
            stdout=self.lines.append,
            caam_runner=lambda *, args: _CaamResult(
                returncode=0,
                stdout=json.dumps({"tools": [{"tool": "claude", "active_profile": ACTIVE}]}),
            ),
            fetcher=self.fetch,
            save_state=lambda *, state, state_path: None,
            push_post=self.post,
        )

    def report(self) -> str:
        return "\n".join(self.lines)

    def stored(self) -> dict[str, object]:
        return json.loads((self.root / CONDITIONS_REL).read_text(encoding="utf-8"))


def _pass(*, tmp_path: Path, **setup: bool) -> _Pass:
    return _Pass(root=tmp_path).setup(**setup).probe_list()


def test_a_persisting_unusable_factory_credential_is_not_realerted_before_its_repeat_interval(
    *, tmp_path: Path
) -> None:
    """A one-hour-old alert remains quiet when the default interval is six hours."""
    scenario = _pass(tmp_path=tmp_path).condition(alerted_ago=HOUR)
    scenario.reply = (_usage(weekly=0.0), None)

    assert scenario.run() == 0

    assert f"{KEY}: unusable" in scenario.report()
    assert scenario.pushed == []


def test_a_rate_limited_factory_credential_probe_is_inconclusive_and_not_alerted(
    *, tmp_path: Path
) -> None:
    """A rate limit produces an inconclusive report line without a push alert."""
    scenario = _pass(tmp_path=tmp_path)
    scenario.reply = (None, "HTTP 429")

    assert scenario.run() == 0

    assert f"{KEY}: inconclusive" in scenario.report()
    assert scenario.pushed == []


def test_an_unreadable_factory_credential_is_unusable_and_alerted_with_its_identity(
    *, tmp_path: Path
) -> None:
    """An unreadable configured location is a reportable unusable credential."""
    scenario = _pass(tmp_path=tmp_path, readable=False)

    assert scenario.run() == 0

    assert f"{KEY}: unusable" in scenario.report()
    assert scenario.probes == 0
    assert len(scenario.pushed) == 1
    assert "factory-a" in scenario.pushed[0]
    assert "tenant-a" in scenario.pushed[0]


def test_a_recovered_factory_credential_sends_exactly_one_recovery_alert(*, tmp_path: Path) -> None:
    """A usable reading after an unusable alert delivers one recovery notification."""
    scenario = _pass(tmp_path=tmp_path).condition(alerted_ago=HOUR)

    assert scenario.run() == 0
    assert scenario.run(at=NOW + 2 * HOUR) == 0

    assert f"{KEY}: usable" in scenario.report()
    assert len(scenario.pushed) == 1
    assert "recovered" in scenario.pushed[0]


def test_a_report_states_when_no_push_channel_is_configured(*, tmp_path: Path) -> None:
    """The report makes an absent delivery channel visible to the operator."""
    scenario = _pass(tmp_path=tmp_path, channel=False)

    assert scenario.run() == 0

    assert "alerts cannot be delivered" in scenario.report()
    assert scenario.pushed == []


def test_an_unusable_credential_alerts_once_then_repeats_after_the_interval(
    *, tmp_path: Path
) -> None:
    """The onset alert names the condition; a persisting condition repeats once per interval."""
    scenario = _pass(tmp_path=tmp_path)
    scenario.reply = (None, "OAuth token has expired")
    scenario.probe_list(extra={"probe_interval_seconds": HOUR, "repeat_interval_seconds": 6 * HOUR})

    assert scenario.run() == 0
    assert scenario.run(at=NOW + 2 * HOUR) == 0
    assert len(scenario.pushed) == 1
    assert "unusable" in scenario.pushed[0]
    assert scenario.run(at=NOW + 7 * HOUR) == 0

    assert len(scenario.pushed) == 2
    assert "still unusable" in scenario.pushed[1]
    assert "credentials" not in "".join(scenario.pushed).lower()


def test_an_exhausted_window_judges_the_credential_unusable(*, tmp_path: Path) -> None:
    """A short window at zero is as unusable as a weekly one."""
    scenario = _pass(tmp_path=tmp_path)
    scenario.reply = (_usage(short=0.0), None)

    assert scenario.run() == 0

    assert f"{KEY}: unusable" in scenario.report()
    assert len(scenario.pushed) == 1


def test_a_usable_credential_with_no_prior_alert_sends_nothing(*, tmp_path: Path) -> None:
    """Nothing is delivered when nothing was ever alerted."""
    scenario = _pass(tmp_path=tmp_path)

    assert scenario.run() == 0

    assert f"{KEY}: usable" in scenario.report()
    assert scenario.pushed == []


def test_a_failed_delivery_is_reported_and_retried_on_the_next_pass(*, tmp_path: Path) -> None:
    """The condition is not recorded as alerted until a delivery succeeds."""
    scenario = _pass(tmp_path=tmp_path)
    scenario.reply = (None, "HTTP 401")
    scenario.push_outcome = "failed OSError"

    assert scenario.run() == 0
    assert "alert delivery failed" in scenario.report()
    scenario.push_outcome = "sent 200"
    assert scenario.run(at=NOW + 2 * HOUR) == 0

    assert len(scenario.pushed) == 2
    assert scenario.stored()["conditions"] != {}


def test_a_failed_recovery_and_a_failed_repeat_keep_the_condition_for_retry(
    *, tmp_path: Path
) -> None:
    """A recovery or a repeat that cannot be delivered leaves the prior condition standing."""
    scenario = _pass(tmp_path=tmp_path).condition(alerted_ago=7 * HOUR)
    scenario.push_outcome = "failed OSError"

    assert scenario.run() == 0
    assert scenario.stored()["conditions"] != {}
    scenario.reply = (_usage(weekly=0.0), None)
    assert scenario.run(at=NOW + 2 * HOUR) == 0

    assert len(scenario.pushed) == 2
    assert scenario.stored()["conditions"] != {}


def test_the_probe_waits_out_its_interval_but_the_report_still_shows_the_last_verdict(
    *, tmp_path: Path
) -> None:
    """A second pass inside the probe interval reads nothing and reports the stored verdict."""
    scenario = _pass(tmp_path=tmp_path)

    assert scenario.run() == 0
    scenario.lines.clear()
    assert scenario.run(at=NOW + 60.0) == 0

    assert scenario.probes == 1
    assert f"{KEY}: usable" in scenario.report()


def test_a_dry_run_probes_and_alerts_nothing(*, tmp_path: Path) -> None:
    """A dry run neither reads the provider for a probe nor delivers nor records."""
    scenario = _pass(tmp_path=tmp_path, readable=False)

    assert scenario.run(dry_run=True) == 0

    assert scenario.pushed == []
    assert not (tmp_path / CONDITIONS_REL).exists()


def test_an_unscheduled_manual_pass_reads_no_credential_and_sends_no_alert(
    *, tmp_path: Path
) -> None:
    """Factory probes run on scheduled passes only, never on an explicit manual rotation."""
    scenario = _pass(tmp_path=tmp_path, readable=False)

    assert scenario.run(scheduled=False) == 0

    assert scenario.probes == 0
    assert scenario.pushed == []
    assert not (tmp_path / CONDITIONS_REL).exists()


def test_a_pass_without_a_probe_list_reports_nothing_about_probes(*, tmp_path: Path) -> None:
    """The probe stage is silent until a probe list is configured."""
    scenario = _Pass(root=tmp_path).setup(channel=False)

    assert scenario.run() == 0

    assert "alerts cannot be delivered" not in scenario.report()
    assert scenario.probes == 0


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "[]",
        json.dumps({"credentials": "nope"}),
        json.dumps({"credentials": [{"label": "a"}]}),
        json.dumps({"credentials": [], "probe_interval_seconds": "soon"}),
    ],
)
def test_a_malformed_probe_list_is_reported_and_probes_nothing(
    *, tmp_path: Path, body: str
) -> None:
    """A probe list that cannot be understood is said so, never silently skipped."""
    scenario = _Pass(root=tmp_path).setup()
    path = tmp_path / PROBE_LIST_REL
    path.parent.mkdir(parents=True)
    _ = path.write_text(body, encoding="utf-8")

    assert scenario.run() == 0

    assert "factory probe list is malformed" in scenario.report()
    assert scenario.probes == 0


def test_a_corrupt_conditions_file_is_treated_as_no_prior_condition(*, tmp_path: Path) -> None:
    """Damaged memory costs at most a repeated alert, never a failed pass."""
    scenario = _pass(tmp_path=tmp_path)
    scenario.reply = (None, "HTTP 401")
    path = tmp_path / CONDITIONS_REL
    path.parent.mkdir(parents=True)
    _ = path.write_text("{", encoding="utf-8")

    assert scenario.run() == 0

    assert len(scenario.pushed) == 1
