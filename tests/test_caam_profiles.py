"""Tests for caam profile enumeration, usage cache, and state persistence."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import ModuleType

import pytest
from caam_decision import UsageRecord

__all__: list[str] = []


def caam_profiles_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_profiles.py"
    assert module_path.is_file()
    return importlib.import_module("caam_profiles")


def usage(
    *,
    five_hour: float = 20.0,
    seven_day: float = 30.0,
    five_hour_resets_at: str | None = "2026-08-21T12:00:00Z",
    seven_day_resets_at: str | None = "2026-08-25T12:00:00Z",
    fable: float | None = 40.0,
    fable_resets_at: str | None = "2026-08-25T12:00:00Z",
) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at=five_hour_resets_at,
        seven_day_resets_at=seven_day_resets_at,
        fable=fable,
        fable_resets_at=fable_resets_at,
    )


def test_profile_names_skip_underscore_entries_and_append_missing_active(*, tmp_path: Path):
    module = caam_profiles_module()
    vault = tmp_path / "vault"
    for name in ("anthropic-2", "_original", "anthropic-0"):
        (vault / name).mkdir(parents=True)

    assert module.profile_names(vault=vault, active_name="anthropic-1") == (
        "anthropic-0",
        "anthropic-2",
        "anthropic-1",
    )


def test_missing_vault_still_lists_the_active_profile(*, tmp_path: Path):
    module = caam_profiles_module()

    assert module.profile_names(vault=tmp_path / "missing", active_name="active") == ("active",)


def test_poll_profiles_uses_live_creds_for_active_and_snapshot_for_others(*, tmp_path: Path):
    module = caam_profiles_module()
    home = tmp_path
    vault = home / ".local" / "share" / "caam" / "vault" / "claude"
    (vault / "active").mkdir(parents=True)
    (vault / "other").mkdir()
    (vault / "_original").mkdir()
    (vault / "other" / ".credentials.json").write_text("{}", encoding="utf-8")
    (home / ".claude").mkdir()
    (home / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    requested: list[Path] = []

    def fetcher(*, creds_path: Path, now: float | None = None):
        requested.append(creds_path)
        if creds_path == home / ".claude" / ".credentials.json":
            return usage(five_hour=10.0), None
        return usage(five_hour=20.0), None

    state: dict[str, object] = {}
    rows = module.poll_profiles(
        active_name="active", state=state, home=home, now=7200.0, fetcher=fetcher
    )

    assert [row.name for row in rows] == ["active", "other"]
    assert [row.source for row in rows] == ["live", "live"]
    assert requested == [
        home / ".claude" / ".credentials.json",
        vault / "other" / ".credentials.json",
    ]
    assert state["profiles"] == {
        "active": {
            "at": 7200.0,
            "five_hour": 10.0,
            "seven_day": 30.0,
            "five_hour_resets_at": "2026-08-21T12:00:00Z",
            "seven_day_resets_at": "2026-08-25T12:00:00Z",
            "fable": 40.0,
            "fable_resets_at": "2026-08-25T12:00:00Z",
        },
        "other": {
            "at": 7200.0,
            "five_hour": 20.0,
            "seven_day": 30.0,
            "five_hour_resets_at": "2026-08-21T12:00:00Z",
            "seven_day_resets_at": "2026-08-25T12:00:00Z",
            "fable": 40.0,
            "fable_resets_at": "2026-08-25T12:00:00Z",
        },
    }


def test_failed_poll_uses_cache_inside_age_bound_and_dark_outside(*, monkeypatch, tmp_path: Path):
    module = caam_profiles_module()
    monkeypatch.setenv("CAAM_ROTATE_CACHE_MAX_AGE_S", "3600")
    home = tmp_path
    (home / ".claude").mkdir()
    (home / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    state: dict[str, object] = {
        "profiles": {
            "active": {
                "at": 3600.0,
                "five_hour": 12.0,
                "seven_day": 34.0,
                "five_hour_resets_at": "2026-08-21T12:00:00Z",
                "seven_day_resets_at": "2026-08-25T12:00:00Z",
                "fable": None,
                "fable_resets_at": None,
            }
        }
    }

    def fetcher(*, creds_path: Path, now: float | None = None):
        return None, "token expired 1.0h ago"

    cached = module.poll_profiles(
        active_name="active",
        state=state,
        home=home,
        now=7200.0,
        fetcher=fetcher,
    )
    dark = module.poll_profiles(
        active_name="active",
        state=state,
        home=home,
        now=7200.1,
        fetcher=fetcher,
    )

    assert cached[0].source == "cached 1.0h"
    assert cached[0].usage == usage(
        five_hour=12.0, seven_day=34.0, fable=None, fable_resets_at=None
    )
    assert dark[0].source == "dark: token expired 1.0h ago"
    assert dark[0].usage is None


def test_poll_profiles_reports_missing_snapshot_as_dark_without_fetching(*, tmp_path: Path):
    module = caam_profiles_module()
    home = tmp_path
    vault = home / ".local" / "share" / "caam" / "vault" / "claude"
    (vault / "other").mkdir(parents=True)
    fetched: list[Path] = []

    def fetcher(*, creds_path: Path, now: float | None = None):
        fetched.append(creds_path)
        return usage(), None

    rows = module.poll_profiles(
        active_name=None,
        state={},
        home=home,
        now=1000.0,
        fetcher=fetcher,
    )

    assert rows[0].source == "dark: no snapshot"
    assert rows[0].usage is None
    assert fetched == []


def test_load_state_returns_empty_mapping_for_missing_malformed_or_non_object(*, tmp_path: Path):
    module = caam_profiles_module()
    state_path = tmp_path / "state.json"

    assert module.load_state(state_path=state_path) == {}

    state_path.write_text("[1]", encoding="utf-8")
    assert module.load_state(state_path=state_path) == {}

    state_path.write_text("{", encoding="utf-8")
    assert module.load_state(state_path=state_path) == {}


def test_save_state_creates_private_directory_and_file_atomically(*, tmp_path: Path):
    module = caam_profiles_module()
    state_path = tmp_path / "state" / "state.json"

    module.save_state(state={"profiles": {"active": {"at": 1.0}}}, state_path=state_path)

    assert stat_mode(path=state_path.parent) == 0o700
    assert stat_mode(path=state_path) == 0o600
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "profiles": {"active": {"at": 1.0}}
    }
    assert state_path.read_text(encoding="utf-8") == (
        "{\n" ' "profiles": {\n' '  "active": {\n' '   "at": 1.0\n' "  }\n" " }\n" "}"
    )


def test_interrupted_state_write_does_not_replace_existing_file(*, monkeypatch, tmp_path: Path):
    module = caam_profiles_module()
    state_path = tmp_path / "state" / "state.json"
    module.save_state(state={"profiles": {"active": {"at": 1.0}}}, state_path=state_path)

    def fail_replace(
        src: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        dst: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    ) -> None:
        del src, dst
        raise OSError("interrupted")

    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="interrupted"):
        module.save_state(state={"profiles": {"active": {"at": 2.0}}}, state_path=state_path)

    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "profiles": {"active": {"at": 1.0}}
    }


def stat_mode(*, path: Path) -> int:
    return path.stat().st_mode & 0o777
