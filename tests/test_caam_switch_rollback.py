"""Coverage for rollback when post-activation state repair fails."""

from __future__ import annotations

import importlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from caam_decision import ProfileUsage, UsageRecord


def test_post_activation_error_restores_captured_live_files(*, monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("caam_switch")
    credential = tmp_path / ".claude/.credentials.json"
    profile = tmp_path / ".claude.json"
    settings = tmp_path / ".claude/settings.json"
    target = tmp_path / ".local/share/caam/vault/claude/target/.claude.json"
    credential.parent.mkdir(parents=True)
    settings.parent.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True)
    credential.write_bytes(b"live credential\n")
    profile.write_text('{"oauthAccount":{"accountUuid":"active"},"userID":"active"}\n')
    settings.write_text('{"effortLevel":"high"}\n')
    target.write_text('{"oauthAccount":{"accountUuid":"target"},"userID":"target"}\n')
    before = tuple(path.read_bytes() for path in (credential, profile, settings))

    def fail_after_activation(*, state: object) -> None:
        del state
        raise RuntimeError("state repair failed")

    monkeypatch.setattr(module, "apply_activated_state", fail_after_activation)
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
            activator=lambda *, args, timeout: SimpleNamespace(returncode=0, stdout="", stderr=""),
            lock_factory=lambda *, lock_path: nullcontext(),
            save=lambda *, state: None,
        )
    )

    assert result.exit_code == 2
    assert result.lines == ("FAIL RuntimeError: state repair failed",)
    assert tuple(path.read_bytes() for path in (credential, profile, settings)) == before


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
