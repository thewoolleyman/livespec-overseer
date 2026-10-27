"""Coverage for rollback when post-activation state repair fails."""

from __future__ import annotations

import importlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from caam_decision import ProfileUsage, UsageRecord


def _write_live_files(*, credential: Path, profile: Path, settings: Path, target: Path) -> None:
    credential.write_bytes(b"live credential\n")
    profile.write_text('{"oauthAccount":{"accountUuid":"active"},"userID":"active"}\n')
    settings.write_text('{"effortLevel":"high"}\n')
    target.write_text('{"oauthAccount":{"accountUuid":"target"},"userID":"target"}\n')


def test_post_activation_error_restores_captured_live_files(*, monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("caam_switch")
    state_module = importlib.import_module("_caam_switch_state")
    credential = tmp_path / ".claude/.credentials.json"
    profile = tmp_path / ".claude.json"
    settings = tmp_path / ".claude/settings.json"
    target = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    credential.parent.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True)
    _write_live_files(
        credential=credential,
        profile=profile,
        settings=settings,
        target=target,
    )
    before = tuple(path.read_bytes() for path in (credential, profile, settings))

    writes: list[Path] = []
    atomic_write = state_module._atomic_write

    def fail_profile_write_after_activation(*, path: Path, body: bytes) -> None:
        writes.append(path)
        if path == profile and writes.count(profile) == 1:
            raise OSError("profile write failed")
        atomic_write(path=path, body=body)

    def install_then_succeed(**_: object) -> SimpleNamespace:
        credential.write_bytes(b"installed credential\n")
        profile.write_text('{"oauthAccount":{"accountUuid":"target"},"userID":"target"}\n')
        settings.write_text('{"effortLevel":"low"}\n')
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(state_module, "_atomic_write", fail_profile_write_after_activation)
    usage = UsageRecord(
        five_hour_remaining=10.0,
        seven_day_remaining=10.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )
    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage),
            current=usage,
            state={},
            home=tmp_path,
            now=0.0,
            active_reader=lambda: "active",
            fetcher=lambda *, creds_path, now: (usage, None),
            activator=install_then_succeed,
            lock_factory=lambda *, lock_path: nullcontext(),
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 2
    assert result.reason == module.REASON_FAIL_POST_INSTALL_WRITE
    assert result.lines == (
        "FAIL switch to target: post-install write failed "
        "(OSError: profile write failed); restored pre-switch state.",
    )
    assert writes == [profile, credential, profile, settings]
    assert tuple(path.read_bytes() for path in (credential, profile, settings)) == before


def test_post_activation_error_names_every_file_the_restore_cannot_write(
    *, monkeypatch, tmp_path: Path
) -> None:
    module = importlib.import_module("caam_switch")
    state_module = importlib.import_module("_caam_switch_state")
    credential = tmp_path / ".claude/.credentials.json"
    profile = tmp_path / ".claude.json"
    settings = tmp_path / ".claude/settings.json"
    target = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    credential.parent.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True)
    _write_live_files(
        credential=credential,
        profile=profile,
        settings=settings,
        target=target,
    )
    writes: list[Path] = []
    atomic_write = state_module._atomic_write

    def fail_write_and_two_restores(*, path: Path, body: bytes) -> None:
        writes.append(path)
        if path == profile and writes.count(profile) == 1:
            raise OSError("profile write failed")
        if path in (credential, settings):
            raise OSError(f"cannot restore {path.name}")
        atomic_write(path=path, body=body)

    usage = UsageRecord(
        five_hour_remaining=10.0,
        seven_day_remaining=10.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )
    monkeypatch.setattr(state_module, "_atomic_write", fail_write_and_two_restores)
    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage),
            current=usage,
            state={},
            home=tmp_path,
            now=0.0,
            active_reader=lambda: "active",
            fetcher=lambda *, creds_path, now: (usage, None),
            activator=lambda *, args, timeout: SimpleNamespace(returncode=0, stdout="", stderr=""),
            lock_factory=lambda *, lock_path: nullcontext(),
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 2
    assert result.reason == "fail-restore"
    assert result.lines == (
        "FAIL switch to target: post-install write failed "
        "(OSError: profile write failed); restoration failed for "
        f"{credential}, {settings}.",
    )
    assert writes == [profile, credential, profile, settings]


def test_failed_activation_reports_every_file_the_restore_cannot_write(
    *, monkeypatch, tmp_path: Path
) -> None:
    module = importlib.import_module("caam_switch")
    state_module = importlib.import_module("_caam_switch_state")
    credential = tmp_path / ".claude/.credentials.json"
    profile = tmp_path / ".claude.json"
    settings = tmp_path / ".claude/settings.json"
    target = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    credential.parent.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True)
    _write_live_files(
        credential=credential,
        profile=profile,
        settings=settings,
        target=target,
    )
    writes: list[Path] = []
    atomic_write = state_module._atomic_write

    def fail_two_restores(*, path: Path, body: bytes) -> None:
        writes.append(path)
        if path in (credential, settings):
            raise OSError(f"cannot restore {path.name}")
        atomic_write(path=path, body=body)

    usage = UsageRecord(
        five_hour_remaining=10.0,
        seven_day_remaining=10.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )
    monkeypatch.setattr(state_module, "_atomic_write", fail_two_restores)
    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage),
            current=usage,
            state={},
            home=tmp_path,
            now=0.0,
            active_reader=lambda: "active",
            fetcher=lambda *, creds_path, now: (usage, None),
            activator=lambda *, args, timeout: SimpleNamespace(
                returncode=1, stdout="", stderr="no"
            ),
            lock_factory=lambda *, lock_path: nullcontext(),
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 2
    assert result.reason == module.REASON_FAIL_RESTORE
    assert result.lines == (
        "FAIL switch to target: restoration failed for " f"{credential}, {settings}.",
    )
    assert writes == [credential, profile, settings]


def test_did_not_stick_reports_every_file_the_restore_cannot_write(
    *, monkeypatch, tmp_path: Path
) -> None:
    module = importlib.import_module("caam_switch")
    recovery = importlib.import_module("_caam_switch_recovery")
    state_module = importlib.import_module("_caam_switch_state")
    credential = tmp_path / ".claude/.credentials.json"
    profile = tmp_path / ".claude.json"
    settings = tmp_path / ".claude/settings.json"
    target = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    credential.parent.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True)
    _write_live_files(
        credential=credential,
        profile=profile,
        settings=settings,
        target=target,
    )
    writes: list[Path] = []
    atomic_write = state_module._atomic_write

    def fail_two_restores(*, path: Path, body: bytes) -> None:
        writes.append(path)
        if path == credential or (path == settings and writes.count(settings) == 2):
            raise OSError(f"cannot restore {path.name}")
        atomic_write(path=path, body=body)

    usage = UsageRecord(
        five_hour_remaining=10.0,
        seven_day_remaining=10.0,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )
    monkeypatch.setattr(state_module, "_atomic_write", fail_two_restores)
    monkeypatch.setattr(recovery, "switch_did_not_stick", lambda **_: True)
    result = module.switch_account(
        request=module.SwitchRequest(
            active_name="active",
            target=ProfileUsage(name="target", source="live", usage=usage),
            current=usage,
            state={},
            home=tmp_path,
            now=0.0,
            active_reader=lambda: "active",
            fetcher=lambda *, creds_path, now: (usage, None),
            activator=lambda *, args, timeout: SimpleNamespace(returncode=0, stdout="", stderr=""),
            lock_factory=lambda *, lock_path: nullcontext(),
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 2
    assert result.reason == module.REASON_FAIL_RESTORE
    assert result.lines == (
        "FAIL switch to target: restoration failed for " f"{credential}, {settings}.",
    )
    assert writes == [profile, settings, credential, profile, settings]


@pytest.mark.parametrize("profile_body", [b"not json", b"[]"])
def test_capture_rejects_invalid_live_global_state(*, profile_body: bytes, tmp_path: Path) -> None:
    state = importlib.import_module("_caam_switch_state")
    credential = tmp_path / ".claude/.credentials.json"
    profile = tmp_path / ".claude.json"
    settings = tmp_path / ".claude/settings.json"
    target = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    credential.parent.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True)
    credential.write_bytes(b"live credential\n")
    profile.write_bytes(profile_body)
    settings.write_text("{}\n")
    target.write_text('{"oauthAccount":{},"userID":"target"}\n')

    with pytest.raises(state.StateValidationError, match=r"\.claude\.json"):
        state.capture_live_state(home=tmp_path, target_name="target")


def test_atomic_restore_cleans_up_temporary_file_after_write_failure(
    *, monkeypatch, tmp_path: Path
) -> None:
    state = importlib.import_module("_caam_switch_state")
    destination = tmp_path / "settings.json"
    destination.write_bytes(b"before\n")

    monkeypatch.setattr(Path, "replace", Mock(side_effect=OSError("replace failed")))

    with pytest.raises(OSError, match="replace failed"):
        state._atomic_write(path=destination, body=b"after\n")

    assert destination.read_bytes() == b"before\n"
    assert list(tmp_path.glob("settings.json.*")) == []
