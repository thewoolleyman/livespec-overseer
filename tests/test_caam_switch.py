"""Tests for caam account switch serialization and verification."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

from caam_decision import ProfileUsage, UsageRecord, eligible_profiles, rank_profiles

__all__: list[str] = []


def caam_switch_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_switch.py"
    assert module_path.is_file()
    return importlib.import_module("caam_switch")


def usage(
    *,
    five_hour: float = 20.0,
    seven_day: float = 30.0,
    seven_day_resets_at: str | None = "2026-08-22T00:00:00Z",
) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-21T12:00:00Z",
        seven_day_resets_at=seven_day_resets_at,
        fable=None,
        fable_resets_at=None,
    )


class FakeLock:
    def __init__(self, *, acquired: bool = True) -> None:
        self.acquired = acquired
        self.entered = False
        self.released = False

    def __enter__(self) -> FakeLock:
        self.entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        del exc_type, exc, traceback
        self.released = True
        return False


class FakeLockFactory:
    def __init__(self, *, lock: FakeLock | None) -> None:
        self.lock = lock
        self.paths: list[Path] = []

    def __call__(self, *, lock_path: Path):
        self.paths.append(lock_path)
        return self.lock


class FakeProcess:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeActivator:
    def __init__(
        self, *, process: FakeProcess | None = None, exc: BaseException | None = None
    ) -> None:
        self.process = process or FakeProcess()
        self.exc = exc
        self.calls: list[tuple[str, ...]] = []
        self.lock: FakeLock | None = None

    def __call__(self, *, args: tuple[str, ...], timeout: float) -> FakeProcess:
        del timeout
        self.calls.append(args)
        if self.exc is not None:
            raise self.exc
        assert self.lock is not None
        assert not self.lock.released
        return self.process


class FakeActive:
    def __init__(self, *profiles: str | None) -> None:
        self.profiles = list(profiles)

    def __call__(self) -> str | None:
        return self.profiles.pop(0)


def write_creds(*, path: Path, access_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": access_value, "expiresAt": 9999999999000}}),
        encoding="utf-8",
    )


def test_contended_lock_holds_without_waiting_and_saves_state(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    lock_factory = FakeLockFactory(lock=None)

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1000.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=FakeActivator(),
            lock_factory=lock_factory,
            save=lambda *, state: saved.append(dict(state)),
        )
    )

    assert result.exit_code == 0
    assert result.lines == ("hold: another caam-anthropic-loop holds the switch lock",)
    assert saved == [{"profiles": {}}]
    assert lock_factory.paths == [tmp_path / ".local/state/caam-usage-rotate/switch.lock"]


def test_active_change_under_lock_abandons_stale_decision_and_saves(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    lock = FakeLock()

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1000.0,
            active_reader=FakeActive("new-active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=FakeActivator(),
            lock_factory=FakeLockFactory(lock=lock),
            save=lambda *, state: saved.append(dict(state)),
        )
    )

    assert result.exit_code == 0
    assert result.lines == (
        "hold: active changed active -> new-active while deciding; re-evaluating next tick",
    )
    assert saved == [{"profiles": {}}]
    assert lock.released


def test_destination_reprobe_failure_refuses_switch_and_saves(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    activator = FakeActivator()

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1000.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (None, "token expired 1.0h ago"),
            activator=activator,
            lock_factory=FakeLockFactory(lock=FakeLock()),
            save=lambda *, state: saved.append(dict(state)),
        )
    )

    assert result.exit_code == 2
    assert result.lines == (
        "FAIL refusing to switch to target -- its stored credential does not work right now "
        "(token expired 1.0h ago). Installing it would break every running session.",
    )
    assert activator.calls == []
    assert saved == [{"profiles": {}}]


def test_activation_failure_releases_lock_saves_and_exits_2(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    lock = FakeLock()
    activator = FakeActivator(process=FakeProcess(returncode=1, stdout="stdout", stderr="nope\n"))
    activator.lock = lock

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1000.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=activator,
            lock_factory=FakeLockFactory(lock=lock),
            save=lambda *, state: saved.append(dict(state)),
        )
    )

    assert result.exit_code == 2
    assert result.lines == ("FAIL caam activate target: nope",)
    assert activator.calls == [("activate", "claude", "target")]
    assert lock.released
    assert saved == [{"profiles": {}}]


def test_activation_exception_releases_lock_saves_and_reports_fail(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    lock = FakeLock()
    activator = FakeActivator(exc=RuntimeError("boom"))
    activator.lock = lock

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1000.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=activator,
            lock_factory=FakeLockFactory(lock=lock),
            save=lambda *, state: saved.append(dict(state)),
        )
    )

    assert result.exit_code == 2
    assert result.lines == ("FAIL RuntimeError: boom",)
    assert lock.released
    assert saved == [{"profiles": {}}]


def test_stick_verification_failure_reports_fail_after_lock_release_and_saves(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    lock = FakeLock()
    activator = FakeActivator()
    activator.lock = lock
    write_creds(
        path=tmp_path / ".local/share/caam/vault/claude/target/.credentials.json",
        access_value="target-value",
    )
    write_creds(path=tmp_path / ".claude/.credentials.json", access_value="other-value")

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1000.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=activator,
            lock_factory=FakeLockFactory(lock=lock),
            save=lambda *, state: saved.append(dict(state)),
        )
    )

    assert result.exit_code == 2
    assert result.lines == (
        "FAIL switch to target did not stick -- the live credential no longer matches the "
        "snapshot. A running Claude session most likely refreshed its own token over the "
        "swap. Re-run to retry.",
    )
    assert lock.released
    assert saved == [{"profiles": {}}]


def test_success_records_last_switch_saves_and_reports_switch(*, tmp_path: Path):
    module = caam_switch_module()
    saved: list[dict[str, object]] = []
    lock = FakeLock()
    activator = FakeActivator()
    activator.lock = lock
    write_creds(
        path=tmp_path / ".local/share/caam/vault/claude/target/.credentials.json",
        access_value="target-value",
    )
    write_creds(path=tmp_path / ".claude/.credentials.json", access_value="target-value")

    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage(seven_day=25.0)),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=tmp_path,
            now=1787356770.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=activator,
            lock_factory=FakeLockFactory(lock=lock),
            save=lambda *, state: saved.append(json.loads(json.dumps(state))),
        )
    )

    assert result.exit_code == 0
    assert result.lines == (
        "SWITCHED active -> target (5h left was 10%; target has 75% week left resetting in "
        "0m -- soonest, live)",
    )
    assert saved == [
        {"profiles": {}, "last_switch": {"at": 1787356770.0, "from": "active", "to": "target"}}
    ]


def test_cached_row_is_never_selected_even_when_it_would_rank_first():
    current = usage(five_hour=95.0, seven_day=80.0)
    cached_best = ProfileUsage(
        name="cached-best",
        source="cached 0.1h",
        usage=usage(
            five_hour=10.0,
            seven_day=10.0,
            seven_day_resets_at="2026-08-21T00:00:00Z",
        ),
    )
    live_later = ProfileUsage(
        name="live-later",
        source="live",
        usage=usage(
            five_hour=20.0,
            seven_day=20.0,
            seven_day_resets_at="2026-08-25T00:00:00Z",
        ),
    )

    candidates = eligible_profiles(
        profiles=(cached_best, live_later),
        active_name="active",
        current=current,
        force=True,
        dimension="five_hour",
    ).profiles

    assert [profile.name for profile in rank_profiles(profiles=candidates)] == ["live-later"]
