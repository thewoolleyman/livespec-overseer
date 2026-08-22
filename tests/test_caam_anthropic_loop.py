"""Tests for the caam account-rotation executable."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest
from caam_decision import UsageRecord

__all__: list[str] = []


def caam_loop_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_anthropic_loop.py"
    assert module_path.is_file()
    return importlib.import_module("caam_anthropic_loop")


def usage(
    *,
    five_hour: float = 20.0,
    seven_day: float = 30.0,
    seven_day_resets_at: str | None = "2026-08-24T00:00:00Z",
) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at=seven_day_resets_at,
        fable=10.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


class FakeProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'


def test_console_script_registers_the_caam_operation():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'caam-anthropic-loop = "overseer.caam_anthropic_loop:main"' in pyproject


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], {"scheduled": False, "force": False, "dry_run": False}),
        (["--scheduled"], {"scheduled": True, "force": False, "dry_run": False}),
        (["--force", "--dry-run"], {"scheduled": False, "force": True, "dry_run": True}),
        (["--NO-MODELS", "--no-warm"], {"no_models": True, "no_warm": True}),
        (["--foreman-model= FABLE "], {"foreman_model": "fable"}),
        (["--foreman-model", " Opus "], {"foreman_model": "opus"}),
        (["--foreman-model= AUTO "], {"foreman_model": "auto"}),
    ],
)
def test_flags_use_prefix_matching_lowercasing_and_absent_none(*, argv, expected):
    module = caam_loop_module()

    parsed = module.parse_flags(argv=argv)

    for key, value in expected.items():
        assert getattr(parsed, key) == value
    if "foreman_model" not in expected:
        assert parsed.foreman_model is None


def test_unexpected_exception_reports_fail_type_without_traceback():
    module = caam_loop_module()
    out: list[str] = []

    code = module.main(
        argv=[],
        stdout=out.append,
        pass_runner=lambda *, flags: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert code == 2
    assert out == ["FAIL RuntimeError: boom"]


def test_empty_vault_fails_loud_and_saves_state(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        save_state=lambda *, state, state_path: saved.append(dict(state)),
    )

    assert result == 2
    assert out == ["FAIL no profiles found in the caam vault for claude"]
    assert saved == [{}]


def test_active_usage_unreadable_fails_loud_and_saves_state(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    vault_profile = tmp_path / ".local/share/caam/vault/claude/active"
    vault_profile.mkdir(parents=True)

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=lambda *, creds_path, now=None: (None, "HTTP 429"),
        save_state=lambda *, state, state_path: saved.append(dict(state)),
    )

    assert result == 2
    assert out == ["FAIL could not read usage for active profile active: HTTP 429"]
    assert saved == [{"profiles": {}}]


def test_unverified_live_rows_are_not_considered_and_get_revive_note(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "dark"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return None, "no token in snapshot"

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert any(
        line
        == (
            "note: dark could not be verified live and was not considered; "
            "revive it with caam-anthropic-loop --no-warm after refreshing its snapshot"
        )
        for line in out
    )
    assert saved


def test_dry_run_returns_zero_and_saves_state(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "target"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return usage(five_hour=20.0, seven_day=10.0), None

    result = module.run_pass(
        flags=module.parse_flags(argv=["--dry-run"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert any(line.startswith("DRY-RUN would switch active -> target") for line in out)
    assert saved


def test_switch_path_returns_switch_result_and_preserves_switch_save(*, tmp_path: Path):
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "target"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return usage(five_hour=20.0, seven_day=10.0), None

    result = module.run_pass(
        flags=module.parse_flags(argv=["--force"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        switch_account=lambda *, request: module.SwitchResult(
            exit_code=0,
            lines=("SWITCHED active -> target",),
        ),
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert out[-1] == "SWITCHED active -> target"
    assert saved
