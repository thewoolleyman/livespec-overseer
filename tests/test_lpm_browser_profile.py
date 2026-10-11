"""Account browser profiles are deterministic and never repair unsafe state."""

from __future__ import annotations

import hashlib
import importlib
import os
import stat
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from overseer._vendor.returns.result import Failure


def _profile_name(*, provider: str, account_id: str) -> str:
    digest = hashlib.sha256()
    for value in (provider, account_id):
        encoded = value.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _safe_parent(*, root: Path) -> Path:
    parent = root / "browser-profiles"
    parent.mkdir(parents=True, mode=0o700)
    return parent


def _assert_first_use_is_deterministic(*, profile_module: ModuleType, tmp_path: Path) -> None:
    state = tmp_path / "state"
    parent = _safe_parent(root=state)
    expected = parent / _profile_name(provider="anthropic", account_id="account-1")

    first = profile_module.account_profile(
        state_dir=state,
        provider="anthropic",
        account_id="account-1",
        owner_uid=os.geteuid(),
    )
    assert first.unwrap() == expected
    assert stat.S_IMODE(expected.stat().st_mode) == 0o700

    nested = expected / "Default"
    nested.mkdir(mode=0o700)
    preferences = nested / "Preferences"
    preferences.write_bytes(b"safe-state")
    preferences.chmod(0o600)
    second = profile_module.account_profile(
        state_dir=state,
        provider="anthropic",
        account_id="account-1",
        owner_uid=os.geteuid(),
    )
    assert second.unwrap() == expected
    assert preferences.read_bytes() == b"safe-state"

    arguments = profile_module.chrome_arguments(
        chrome_executable="/usr/bin/google-chrome",
        profile=expected,
    )
    assert arguments[0] == "/usr/bin/google-chrome"
    assert f"--user-data-dir={expected}" in arguments
    assert "--remote-debugging-pipe" in arguments
    assert "--disable-sync" in arguments
    assert "--password-store=gnome-libsecret" in arguments
    assert not any(
        forbidden in argument
        for argument in arguments
        for forbidden in ("headless", "extension", "remote-debugging-port", "password-store=basic")
    )


def _assert_unsafe_state_is_untouched(*, profile_module: ModuleType, tmp_path: Path) -> None:
    missing_state = tmp_path / "missing-state"
    missing = profile_module.account_profile(
        state_dir=missing_state,
        provider="anthropic",
        account_id="account-1",
        owner_uid=os.geteuid(),
    )
    assert isinstance(missing, Failure)
    assert not (missing_state / "browser-profiles").exists()
    assert isinstance(
        profile_module.validate_profile(
            profile=missing_state / "browser-profiles",
            owner_uid=os.geteuid(),
        ),
        Failure,
    )

    safe = tmp_path / "safe"
    safe.mkdir(mode=0o700)
    broad = tmp_path / "broad"
    broad.mkdir(mode=0o750)
    wrong_owner = profile_module.validate_profile(profile=safe, owner_uid=os.geteuid() + 1)
    assert isinstance(wrong_owner, Failure)
    assert isinstance(
        profile_module.validate_profile(profile=broad, owner_uid=os.geteuid()),
        Failure,
    )
    assert stat.S_IMODE(broad.stat().st_mode) == 0o750

    file_profile = tmp_path / "profile-file"
    file_profile.write_bytes(b"do-not-replace")
    file_profile.chmod(0o600)
    assert isinstance(
        profile_module.validate_profile(profile=file_profile, owner_uid=os.geteuid()),
        Failure,
    )
    linked = tmp_path / "linked"
    linked.symlink_to(safe, target_is_directory=True)
    assert isinstance(
        profile_module.validate_profile(profile=linked, owner_uid=os.geteuid()),
        Failure,
    )
    assert linked.is_symlink()


def _assert_profile_tree_and_creation_fail_closed(
    *, profile_module: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "tree-state"
    parent = _safe_parent(root=state)
    result = profile_module.account_profile(
        state_dir=state,
        provider="anthropic",
        account_id="unsafe-account",
        owner_uid=os.geteuid(),
    )
    profile = result.unwrap()
    broad_child = profile / "broad-child"
    broad_child.write_bytes(b"unchanged")
    broad_child.chmod(0o640)
    assert isinstance(
        profile_module.validate_profile(profile=profile, owner_uid=os.geteuid()),
        Failure,
    )
    assert stat.S_IMODE(broad_child.stat().st_mode) == 0o640
    broad_child.chmod(0o600)
    (profile / "linked-child").symlink_to(parent, target_is_directory=True)
    assert isinstance(
        profile_module.validate_profile(profile=profile, owner_uid=os.geteuid()),
        Failure,
    )

    failed_state = tmp_path / "failed-state"
    _safe_parent(root=failed_state)
    with monkeypatch.context() as context:
        context.setattr(Path, "mkdir", Mock(side_effect=OSError("no space")))
        failed = profile_module.account_profile(
            state_dir=failed_state,
            provider="anthropic",
            account_id="account-1",
            owner_uid=os.geteuid(),
        )
    assert isinstance(failed, Failure)
    failed_path = (
        failed_state
        / "browser-profiles"
        / _profile_name(provider="anthropic", account_id="account-1")
    )
    assert not failed_path.exists()

    malformed_path = parent / _profile_name(provider="anthropic", account_id="malformed")
    malformed_path.write_bytes(b"preserve")
    malformed_path.chmod(0o600)
    malformed = profile_module.account_profile(
        state_dir=state,
        provider="anthropic",
        account_id="malformed",
        owner_uid=os.geteuid(),
    )
    assert isinstance(malformed, Failure)
    assert malformed_path.read_bytes() == b"preserve"


def test_account_profile_first_use_and_unsafe_state_are_deterministic(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = Path(__file__).parents[1] / "overseer" / "_lpm_browser_profile.py"
    assert module_path.is_file(), "the account browser-profile boundary must be implemented"
    profile_module = importlib.import_module("_lpm_browser_profile")

    _assert_first_use_is_deterministic(profile_module=profile_module, tmp_path=tmp_path)
    _assert_unsafe_state_is_untouched(profile_module=profile_module, tmp_path=tmp_path)
    _assert_profile_tree_and_creation_fail_closed(
        profile_module=profile_module,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
