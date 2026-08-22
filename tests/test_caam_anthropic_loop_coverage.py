"""Supplemental coverage for the caam account-rotation executable."""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from caam_decision import ProfileUsage, UsageRecord

__all__: list[str] = []


def caam_loop_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_anthropic_loop.py"
    assert module_path.is_file()
    return importlib.import_module("caam_anthropic_loop")


def caam_pass_module() -> ModuleType:
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_anthropic_pass.py"
    assert module_path.is_file()
    return importlib.import_module("caam_anthropic_pass")


def usage(*, five_hour: float = 20.0, seven_day: float = 30.0) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at="2026-08-22T12:00:00Z",
        seven_day_resets_at="2026-08-24T00:00:00Z",
        fable=10.0,
        fable_resets_at="2026-08-24T00:00:00Z",
    )


class FakeProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude", "active_profile": "active"}]}'


class NoActiveProcess:
    returncode = 0
    stdout = '{"tools": [{"tool": "claude"}]}'


@dataclass(frozen=True, kw_only=True)
class _Flags:
    force: bool = False
    dry_run: bool = False
    no_models: bool = False
    no_warm: bool = True
    foreman_model: str | None = None


def test_main_default_runner_uses_stdout_and_sys_argv_seams(*, monkeypatch) -> None:
    module = caam_loop_module()
    out: list[str] = []
    seen: list[object] = []

    def fake_run_pass(*, flags, stdout) -> int:
        seen.append(flags)
        stdout("ran")
        return 0

    monkeypatch.setattr(module, "run_pass", fake_run_pass)
    monkeypatch.setattr(module.streams, "write_stdout", lambda *, text: out.append(text))
    monkeypatch.setattr(module.sys, "argv", ["caam-anthropic-loop", "--unknown", "--no-warm"])

    assert module.main() == 0

    assert out == ["ran\n"]
    assert seen[0].no_warm is True


def test_run_pass_default_runner_resolves_active_profile(*, tmp_path: Path, monkeypatch) -> None:
    module = caam_pass_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    (tmp_path / ".local/share/caam/vault/claude/active").mkdir(parents=True)

    monkeypatch.setattr(
        module,
        "caam_activate",
        lambda *, args, timeout: FakeProcess(),
    )

    result = module.run_pass(
        flags=_Flags(),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        fetcher=lambda *, creds_path, now=None: (usage(five_hour=10.0, seven_day=20.0), None),
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        enforce_models=lambda **kwargs: [],
        agent_runner=lambda *, args, env, timeout: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    assert result == 0
    assert saved


def test_no_active_profile_fails_loud_and_saves_state(*, tmp_path: Path) -> None:
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    (tmp_path / ".local/share/caam/vault/claude/active").mkdir(parents=True)

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: NoActiveProcess(),
        save_state=lambda *, state, state_path: saved.append(dict(state)),
    )

    assert result == 2
    assert out == ["FAIL could not determine active claude profile"]
    assert saved == [{}]


def test_hold_path_returns_zero_and_saves_state(*, tmp_path: Path) -> None:
    module = caam_loop_module()
    saved: list[dict[str, object]] = []
    out: list[str] = []
    (tmp_path / ".local/share/caam/vault/claude/active").mkdir(parents=True)

    result = module.run_pass(
        flags=module.parse_flags(argv=["--scheduled"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=lambda *, creds_path, now=None: (usage(five_hour=10.0, seven_day=20.0), None),
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        enforce_models=lambda **kwargs: [],
        agent_runner=lambda *, args, env, timeout: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    assert result == 0
    assert any("left" in line for line in out)
    assert saved


def test_internal_default_seams_are_callable_without_extra_adapters(*, monkeypatch) -> None:
    module = caam_pass_module()
    monkeypatch.setattr(
        module,
        "caam_activate",
        lambda *, args, timeout: FakeProcess(),
    )

    process = module._run_caam(args=("status", "--json"))
    agent = module._run_agent(
        args=(sys.executable, "-c", "print('ok')"),
        env={},
        timeout=5.0,
    )
    reason = module._dark_reason(
        profiles=(ProfileUsage(name="active", usage=None, source="dark: HTTP 429"),),
        active_name="active",
    )
    fallback = module._dark_reason(
        profiles=(ProfileUsage(name="other", usage=None, source="dark: HTTP 429"),),
        active_name="active",
    )

    assert process.returncode != -999
    assert agent.stdout == "ok\n"
    assert reason == "HTTP 429"
    assert fallback == "unreadable"


def test_switch_request_active_reader_uses_decision_default_caam_runner(
    *, tmp_path: Path, monkeypatch
) -> None:
    module = caam_loop_module()
    decide_module = importlib.import_module("caam_anthropic_decide")
    saved: list[dict[str, object]] = []
    out: list[str] = []
    for name in ("active", "target"):
        (tmp_path / ".local/share/caam/vault/claude" / name).mkdir(parents=True)

    monkeypatch.setattr(
        decide_module,
        "caam_activate",
        lambda *, args, timeout: FakeProcess(),
    )

    def fetcher(*, creds_path: Path, now: float | None = None):
        del now
        if creds_path == tmp_path / ".claude/.credentials.json":
            return usage(five_hour=90.0, seven_day=20.0), None
        return usage(five_hour=20.0, seven_day=10.0), None

    def switch_account(*, request):
        assert request.active_reader() == "active"
        return module.SwitchResult(exit_code=0, lines=("SWITCHED active -> target",))

    result = module.run_pass(
        flags=module.parse_flags(argv=["--force"]),
        home=tmp_path,
        now=1787395200.0,
        stdout=out.append,
        caam_runner=lambda *, args: FakeProcess(),
        fetcher=fetcher,
        save_state=lambda *, state, state_path: saved.append(dict(state)),
        switch_account=switch_account,
        enforce_models=lambda **kwargs: [],
    )

    assert result == 0
    assert out[-1] == "SWITCHED active -> target"
    assert saved
