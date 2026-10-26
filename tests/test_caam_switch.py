"""Tests for caam account switch serialization and verification."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    eligible_profiles,
    rank_profiles,
)

__all__: list[str] = []

LOW_EFFORT_SETTINGS = (
    b"{\n"
    b'  "hooks": {"keep": true},\n'
    b'  "effortLevel": "low",\n'
    b'  "plugins": ["keep"]\n'
    b"}\n"
)


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
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at="2026-08-21T12:00:00Z",
        seven_day_resets_at=seven_day_resets_at,
        fable_remaining=None,
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


class OverwritingActivator(FakeActivator):
    def __init__(self, *, paths: tuple[Path, Path, Path]) -> None:
        super().__init__(process=FakeProcess(returncode=1, stderr="rejected"))
        self.paths = paths

    def __call__(self, *, args: tuple[str, ...], timeout: float) -> FakeProcess:
        process = super().__call__(args=args, timeout=timeout)
        for path in self.paths:
            path.write_bytes(b"overwritten by caam\n")
        return process


class InstallingActivator(FakeActivator):
    """A hermetic stand-in for caam restoring a target vault snapshot."""

    def __init__(self, *, installs: tuple[tuple[Path, Path], ...]) -> None:
        super().__init__()
        self.installs = installs

    def __call__(self, *, args: tuple[str, ...], timeout: float) -> FakeProcess:
        process = super().__call__(args=args, timeout=timeout)
        for source, destination in self.installs:
            destination.write_bytes(source.read_bytes())
        return process


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


@pytest.fixture(autouse=True)
def switch_global_state(*, tmp_path: Path) -> None:
    """Seed the state files the switch validates before activation."""
    write_creds(
        path=tmp_path / ".claude/.credentials.json",
        access_value="active-value",
    )
    (tmp_path / ".claude.json").write_text(
        '{"oauthAccount":{"accountUuid":"active"},"userID":"active-user"}\n',
        encoding="utf-8",
    )
    settings = tmp_path / ".claude/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{"effortLevel":"high"}\n', encoding="utf-8")
    stored = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_text(
        '{"oauthAccount":{"accountUuid":"target"},"userID":"target-user"}\n',
        encoding="utf-8",
    )


def test_invalid_stored_global_state_refuses_before_activation_without_changing_live_files(
    *, tmp_path: Path
):
    module = caam_switch_module()
    live_profile = tmp_path / ".claude.json"
    live_settings = tmp_path / ".claude/settings.json"
    live_creds = tmp_path / ".claude/.credentials.json"
    target = tmp_path / ".local/share/caam/vault/claude/target"
    live_profile.write_text(
        '{"oauthAccount":{"accountUuid":"active"},"userID":"active-user"}\n',
        encoding="utf-8",
    )
    live_settings.parent.mkdir(parents=True, exist_ok=True)
    live_settings.write_bytes(b'{"effortLevel":"high"}\n')
    target.mkdir(parents=True, exist_ok=True)
    (target / ".claude.json").write_text(
        '{"oauthAccount":{"accountUuid":"target"}}\n', encoding="utf-8"
    )
    write_creds(path=target / ".credentials.json", access_value="target-value")
    write_creds(path=live_creds, access_value="active-value")
    before = tuple(path.read_bytes() for path in (live_creds, live_profile, live_settings))
    lock = FakeLock()
    activator = FakeActivator()
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
            save=lambda *, state: None,
        )
    )

    assert activator.calls == []
    assert result.exit_code == 2
    assert tuple(path.read_bytes() for path in (live_creds, live_profile, live_settings)) == before


def test_rejected_activation_restores_every_pre_switch_file_byte_for_byte(*, tmp_path: Path):
    module = caam_switch_module()
    live_creds = tmp_path / ".claude/.credentials.json"
    live_profile = tmp_path / ".claude.json"
    live_settings = tmp_path / ".claude/settings.json"
    target_creds = tmp_path / ".local/share/caam/vault/claude/target/.credentials.json"
    write_creds(path=target_creds, access_value="target-value")
    before = tuple(path.read_bytes() for path in (live_creds, live_profile, live_settings))
    lock = FakeLock()
    activator = OverwritingActivator(paths=(live_creds, live_profile, live_settings))
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
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 2
    assert tuple(path.read_bytes() for path in (live_creds, live_profile, live_settings)) == before


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


def switch_snapshot(
    *, home: Path, settings_before: bytes = LOW_EFFORT_SETTINGS
) -> tuple[dict[str, object], bytes, tuple[tuple[Path, Path], ...], Path, Path]:
    """Create live and target files that exercise caam's destructive restore."""
    live_creds = home / ".claude/.credentials.json"
    live_profile = home / ".claude.json"
    live_settings = home / ".claude/settings.json"
    target = home / ".local/share/caam/vault/claude/target"
    target_creds = target / ".credentials.json"
    target_profile = target / ".claude.json"
    target_settings = target / ".claude/settings.json"
    profile_before: dict[str, object] = {
        "oauthAccount": {"accountUuid": "active"},
        "userID": "active-user",
        "hasCompletedOnboarding": True,
        "projects": {"/trusted": {"hasTrustDialogAccepted": True}},
        "otherHostState": ["keep"],
    }
    live_profile.write_text(json.dumps(profile_before), encoding="utf-8")
    live_settings.write_bytes(settings_before)
    write_creds(path=live_creds, access_value="active-value")
    write_creds(path=target_creds, access_value="target-value")
    target_profile.write_text(
        '{"oauthAccount":{"accountUuid":"target"},"userID":"target-user"}\n',
        encoding="utf-8",
    )
    target_settings.parent.mkdir(parents=True)
    target_settings.write_text('{"effortLevel":"medium"}\n', encoding="utf-8")
    return (
        profile_before,
        settings_before,
        (
            (target_creds, live_creds),
            (target_profile, live_profile),
            (target_settings, live_settings),
        ),
        live_profile,
        live_settings,
    )


def switch_from_snapshot(
    *, module: ModuleType, home: Path, installs: tuple[tuple[Path, Path], ...]
):
    """Exercise a successful switch after the fake activator overwrites live files."""
    lock = FakeLock()
    activator = InstallingActivator(installs=installs)
    activator.lock = lock
    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage()),
            current=usage(five_hour=90.0),
            state={"profiles": {}},
            home=home,
            now=1000.0,
            active_reader=FakeActive("active"),
            fetcher=lambda *, creds_path, now=None: (usage(), None),
            activator=activator,
            lock_factory=FakeLockFactory(lock=lock),
            save=lambda *, state: None,
        )
    )
    return result


def test_switch_merges_identity_and_repairs_only_low_effort_under_lock(
    *, monkeypatch, tmp_path: Path
) -> None:
    module = caam_switch_module()
    state_module = importlib.import_module("_caam_switch_state")
    profile_before, settings_before, installs, live_profile, live_settings = switch_snapshot(
        home=tmp_path
    )
    lock = FakeLock()
    activator = InstallingActivator(installs=installs)
    activator.lock = lock
    writes: list[Path] = []
    original_atomic_write = state_module._atomic_write

    def record_atomic_write(*, path: Path, body: bytes) -> None:
        assert lock.entered
        assert not lock.released
        original_atomic_write(path=path, body=body)
        writes.append(path)

    monkeypatch.setattr(state_module, "_atomic_write", record_atomic_write)

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
            save=lambda *, state: None,
        )
    )

    profile_after = json.loads(live_profile.read_text(encoding="utf-8"))
    assert result.switched
    assert profile_after == {
        **profile_before,
        "oauthAccount": {"accountUuid": "target"},
        "userID": "target-user",
    }
    assert live_settings.read_bytes() == settings_before.replace(b'"low"', b'"high"')
    assert writes == [live_profile, live_settings]
    assert live_profile.stat().st_mode & 0o777 == 0o600
    assert live_settings.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("settings_before", "floor", "expected"),
    [
        (b'{"effortLevel":"max"}\n', "high", b'{"effortLevel":"max"}\n'),
        (
            b'{"other":true}\n',
            "high",
            b'{"other":true,\n  "effortLevel": "high"}\n',
        ),
        (b"{}\n", "high", b'{\n  "effortLevel": "high"}\n'),
        (b'{"effortLevel":"custom"}\n', "custom", b'{"effortLevel":"custom"}\n'),
        (b'{"effortLevel":"low"}\n', "", b'{"effortLevel":"low"}\n'),
    ],
)
def test_switch_preserves_settings_that_do_not_need_an_effort_rewrite(
    *, monkeypatch, tmp_path: Path, settings_before: bytes, floor: str, expected: bytes
) -> None:
    module = caam_switch_module()
    monkeypatch.setenv("CAAM_ROTATE_EFFORT", floor)
    _, _, installs, _, live_settings = switch_snapshot(
        home=tmp_path,
        settings_before=settings_before,
    )

    result = switch_from_snapshot(module=module, home=tmp_path, installs=installs)

    assert result.switched
    assert live_settings.read_bytes() == expected


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
        active=ActiveAccount(name="active", usage=current),
        force=True,
        dimension="five_hour",
    ).profiles

    assert [profile.name for profile in rank_profiles(profiles=candidates)] == ["live-later"]
