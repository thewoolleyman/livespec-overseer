"""Production acquisition performers keep local browser and terminal authority closed."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from overseer._lpm_canonical import length_prefixed_digest
from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []


def _write_chrome_standin(*, path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import os
import stat
import sys
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    print("Google Chrome 999.0.0.0")
    raise SystemExit(0)

record = {
    "argv": sys.argv,
    "fd3_fifo": stat.S_ISFIFO(os.fstat(3).st_mode),
    "fd4_fifo": stat.S_ISFIFO(os.fstat(4).st_mode),
}
profile = next(value.split("=", 1)[1] for value in sys.argv if value.startswith("--user-data-dir="))
preferences = Path(profile) / "Default" / "Preferences"
record["preferences"] = json.loads(preferences.read_text()) if preferences.is_file() else None
Path(os.environ["LPM_TEST_CHROME_RECORD"]).write_text(json.dumps(record))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _profile_root(*, state_dir: Path) -> Path:
    root = state_dir / "browser-profiles"
    root.mkdir(parents=True, mode=0o700)
    return root


def _assert_non_chrome_routes_refuse(*, module: ModuleType, tmp_path: Path) -> None:
    extension_only = tmp_path / "extension-only"
    extension_only.mkdir()
    unavailable = module.resolve_installed_google_chrome(
        search_path=(extension_only,),
        environ={"DISPLAY": ":99", "BROWSER": "browser-extension://open"},
        timeout_seconds=1.0,
    )
    assert isinstance(unavailable, Failure)

    chromium_only = tmp_path / "chromium-only"
    chromium_only.mkdir()
    chromium = chromium_only / "chromium"
    chromium.write_text("#!/bin/sh\necho 'Chromium 999.0'\n", encoding="utf-8")
    chromium.chmod(0o755)
    assert isinstance(
        module.resolve_installed_google_chrome(
            search_path=(chromium_only,),
            environ={"WAYLAND_DISPLAY": "wayland-9"},
            timeout_seconds=1.0,
        ),
        Failure,
    )


def _profile_from(*, record: dict[str, object]) -> Path:
    arguments = record["argv"]
    assert isinstance(arguments, list)
    return Path(
        next(
            argument.removeprefix("--user-data-dir=")
            for argument in arguments
            if isinstance(argument, str) and argument.startswith("--user-data-dir=")
        )
    )


def _assert_private_headed_launch(*, module: ModuleType, tmp_path: Path) -> None:
    chrome_bin = tmp_path / "chrome-bin"
    chrome_bin.mkdir()
    chrome = chrome_bin / "google-chrome"
    _write_chrome_standin(path=chrome)
    record_path = tmp_path / "chrome-record.json"
    environment = {
        "DISPLAY": ":99",
        "PATH": os.environ["PATH"],
        "LPM_TEST_CHROME_RECORD": str(record_path),
        "CLAUDE_CODE_OAUTH_TOKEN": "must-not-cross",
        "OP_SERVICE_ACCOUNT_TOKEN": "must-not-cross-either",
    }
    installed = module.resolve_installed_google_chrome(
        search_path=(chrome_bin,),
        environ=environment,
        timeout_seconds=1.0,
    ).unwrap()
    state_dir = tmp_path / "state"
    _profile_root(state_dir=state_dir)
    performer = module.BrowserPerformer(
        chrome=installed,
        state_dir=state_dir,
        owner_uid=os.geteuid(),
        account_home=tmp_path,
        environ=environment,
    )
    first = performer.launch(provider="anthropic", account_id="account-a").unwrap()
    assert first.wait() == 0
    first_record = json.loads(record_path.read_text(encoding="utf-8"))
    first.close()
    second = performer.launch(provider="anthropic", account_id="account-b").unwrap()
    assert second.wait() == 0
    second_record = json.loads(record_path.read_text(encoding="utf-8"))
    second.close()

    assert _profile_from(record=first_record) != _profile_from(record=second_record)
    assert stat.S_IMODE(_profile_from(record=first_record).stat().st_mode) == 0o700
    assert stat.S_IMODE(_profile_from(record=second_record).stat().st_mode) == 0o700
    assert first_record["fd3_fifo"] is first_record["fd4_fifo"] is True
    arguments = first_record["argv"]
    assert "--remote-debugging-pipe" in arguments
    assert not any(
        forbidden in argument
        for argument in arguments
        for forbidden in ("headless", "extension", "remote-debugging-port")
    )


def _browser_fixture(*, module: ModuleType, tmp_path: Path, scope: str) -> tuple[object, Path]:
    fixture_root = tmp_path / scope
    fixture_root.mkdir()
    chrome_bin = fixture_root / "profile-chrome-bin"
    chrome_bin.mkdir()
    chrome = chrome_bin / "google-chrome"
    _write_chrome_standin(path=chrome)
    record_path = fixture_root / "profile-chrome-record.json"
    environment = {
        "DISPLAY": ":99",
        "PATH": os.environ["PATH"],
        "LPM_TEST_CHROME_RECORD": str(record_path),
    }
    installed = module.resolve_installed_google_chrome(
        search_path=(chrome_bin,),
        environ=environment,
        timeout_seconds=1.0,
    ).unwrap()
    state_dir = fixture_root / "profile-state"
    _profile_root(state_dir=state_dir)
    return (
        module.BrowserPerformer(
            chrome=installed,
            state_dir=state_dir,
            owner_uid=os.geteuid(),
            account_home=fixture_root,
            environ=environment,
        ),
        record_path,
    )


def _assert_profile_precedes_launch(*, module: ModuleType, tmp_path: Path) -> None:
    performer, record_path = _browser_fixture(
        module=module,
        tmp_path=tmp_path,
        scope="prepared",
    )
    launched = performer.launch(provider="anthropic", account_id="profile-account").unwrap()
    assert launched.wait() == 0
    launched.close()
    preferences = json.loads(record_path.read_text(encoding="utf-8"))["preferences"]
    assert preferences == {
        "autofill": {"credit_card_enabled": False, "profile_enabled": False},
        "credentials_enable_service": False,
        "profile": {"password_manager_enabled": False},
    }


def _assert_unsafe_profile_and_reference_refuse(*, module: ModuleType, tmp_path: Path) -> None:
    performer, record_path = _browser_fixture(
        module=module,
        tmp_path=tmp_path,
        scope="unsafe",
    )
    unsafe = (
        performer.state_dir
        / "browser-profiles"
        / length_prefixed_digest(values=("anthropic", "unsafe-account"))
    )
    unsafe.mkdir(mode=0o750)
    unsafe.chmod(0o750)
    profile_failure = performer.launch(provider="anthropic", account_id="unsafe-account")
    assert isinstance(profile_failure, Failure)
    assert stat.S_IMODE(unsafe.stat().st_mode) == 0o750
    assert not record_path.exists()

    wrong_owner = replace(performer, owner_uid=os.geteuid() + 1)
    assert isinstance(
        wrong_owner.launch(provider="anthropic", account_id="wrong-owner"),
        Failure,
    )
    changed_binary = replace(performer, chrome=replace(performer.chrome, inode=0))
    assert isinstance(
        changed_binary.launch(provider="anthropic", account_id="changed-binary"),
        Failure,
    )
    assert not record_path.exists()


def _assert_profile_validation_race_refuses(
    *, module: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    performer, record_path = _browser_fixture(
        module=module,
        tmp_path=tmp_path,
        scope="validation-race",
    )
    profile = performer.state_dir / "browser-profiles" / "race-profile"
    profile.mkdir(mode=0o700)
    default = profile / "Default"
    default.mkdir(mode=0o750)
    default.chmod(0o750)

    def raced_profile(
        *, state_dir: Path, provider: str, account_id: str, owner_uid: int
    ) -> Success[Path]:
        assert (state_dir, provider, account_id, owner_uid) == (
            performer.state_dir,
            "anthropic",
            "raced-account",
            os.geteuid(),
        )
        return Success(profile)

    monkeypatch.setattr(module, "account_profile", raced_profile)
    assert isinstance(
        performer.launch(provider="anthropic", account_id="raced-account"),
        Failure,
    )
    assert stat.S_IMODE(default.stat().st_mode) == 0o750
    assert not record_path.exists()


def test_browser_performer_launches_only_installed_headed_chrome_over_private_pipes(
    *, tmp_path: Path
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_browser_performer.py"
    assert module_path.is_file(), "the production browser performer must be implemented"

    import overseer._lpm_browser_performer as module

    _assert_non_chrome_routes_refuse(module=module, tmp_path=tmp_path)
    _assert_private_headed_launch(module=module, tmp_path=tmp_path)


def test_browser_profile_is_prepared_and_unsafe_state_refuses_before_launch(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_browser_preferences.py"
    assert module_path.is_file(), "the pre-launch Chrome preferences boundary must exist"

    import overseer._lpm_browser_performer as module

    _assert_profile_precedes_launch(module=module, tmp_path=tmp_path)
    _assert_unsafe_profile_and_reference_refuse(module=module, tmp_path=tmp_path)
    _assert_profile_validation_race_refuses(
        module=module,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
