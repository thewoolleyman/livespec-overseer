"""Tests for caam active-profile identity resolution."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType

__all__: list[str] = []


def caam_profiles_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_profiles.py"
    assert module_path.is_file()
    return importlib.import_module("caam_profiles")


def write_claude_json(*, path: Path, uuid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"oauthAccount": {"accountUuid": uuid}}), encoding="utf-8")


class FakeCaam:
    def __init__(self, *, returncode: int, stdout: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *, args: tuple[str, ...]) -> object:
        self.calls.append(args)
        return self


def test_caam_status_report_is_preferred_when_present(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    write_claude_json(path=live, uuid="live-uuid")
    write_claude_json(path=vault / "identity-match" / ".claude.json", uuid="live-uuid")
    caam = FakeCaam(
        returncode=0,
        stdout=json.dumps(
            {
                "tools": [
                    {"tool": "other", "active_profile": "wrong-tool"},
                    {"tool": "claude", "active_profile": "caam-report"},
                ]
            }
        ),
    )

    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) == (
        "caam-report"
    )
    assert caam.calls == [("status", "--json")]


def test_uuid_fallback_survives_token_refresh_when_caam_omits_active_profile(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    write_claude_json(path=live, uuid="stable-live-uuid")
    write_claude_json(path=vault / "anthropic-0" / ".claude.json", uuid="other-uuid")
    write_claude_json(path=vault / "anthropic-1" / ".claude.json", uuid="stable-live-uuid")
    caam = FakeCaam(returncode=0, stdout=json.dumps({"tools": [{"tool": "claude"}]}))

    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) == (
        "anthropic-1"
    )


def test_uuid_fallback_tolerates_unreadable_and_malformed_identity_files(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    malformed = vault / "anthropic-0" / ".claude.json"
    write_claude_json(path=live, uuid="stable-live-uuid")
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("[1]", encoding="utf-8")
    write_claude_json(path=vault / "anthropic-1" / ".claude.json", uuid="stable-live-uuid")
    caam = FakeCaam(returncode=0, stdout="{")

    assert module.account_uuid(claude_json_path=tmp_path / "missing.json") is None
    assert module.account_uuid(claude_json_path=malformed) is None
    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) == (
        "anthropic-1"
    )


def test_uuid_fallback_skips_underscore_prefixed_entries(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    write_claude_json(path=live, uuid="stable-live-uuid")
    write_claude_json(path=vault / "_backup" / ".claude.json", uuid="stable-live-uuid")
    write_claude_json(path=vault / "anthropic-2" / ".claude.json", uuid="other-uuid")
    caam = FakeCaam(returncode=1, stdout="")

    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) is None


def test_uuid_fallback_requires_live_uuid_and_vault_directory(*, tmp_path: Path):
    module = caam_profiles_module()
    live = tmp_path / ".claude.json"
    vault = tmp_path / "vault"
    write_claude_json(path=live, uuid="live-uuid")
    caam = FakeCaam(returncode=1, stdout="")

    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) is None

    vault.mkdir()
    live.write_text(json.dumps({"oauthAccount": {}}), encoding="utf-8")
    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) is None


def test_caam_status_ignores_non_object_tool_entries(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    write_claude_json(path=live, uuid="live-uuid")
    caam = FakeCaam(
        returncode=0,
        stdout=json.dumps({"tools": [1, {"tool": "claude", "active_profile": "caam-report"}]}),
    )

    assert module.active_profile(live_account_path=live, vault_path=vault, caam_runner=caam) == (
        "caam-report"
    )


def test_unresolved_active_profile_returns_fail_loud_exit_2(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    write_claude_json(path=live, uuid="live-uuid")
    write_claude_json(path=vault / "anthropic-0" / ".claude.json", uuid="other-uuid")
    caam = FakeCaam(returncode=0, stdout=json.dumps({"tools": []}))

    result = module.resolve_active_profile(
        live_account_path=live,
        vault_path=vault,
        caam_runner=caam,
    )

    assert result.profile is None
    assert result.exit_code == 2
    assert result.message == "FAIL could not determine active claude profile"


def test_resolved_active_profile_returns_success_result(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    live = tmp_path / ".claude.json"
    write_claude_json(path=live, uuid="live-uuid")
    caam = FakeCaam(returncode=0, stdout=json.dumps({"tools": []}))
    write_claude_json(path=vault / "anthropic-0" / ".claude.json", uuid="live-uuid")

    result = module.resolve_active_profile(
        live_account_path=live,
        vault_path=vault,
        caam_runner=caam,
    )

    assert result.profile == "anthropic-0"
    assert result.exit_code == 0
    assert result.message is None
