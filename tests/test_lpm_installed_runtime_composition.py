"""Installed manager surfaces share one command dispatcher.

The package console and flattened plugin executable have different bootstrap
locations, but neither owns command behaviour.  This test pins the common
dispatcher before the later slices exercise recovery and process I/O.
"""

from __future__ import annotations

import importlib
import pathlib
from dataclasses import dataclass, field
from typing import Protocol

import pytest

__all__: list[str] = []


class _Invocation(Protocol):
    command: str


@dataclass(kw_only=True)
class _RecordingRuntime:
    commands: list[str] = field(default_factory=list)

    def run(self, *, invocation: _Invocation) -> str:
        self.commands.append(invocation.command)
        return invocation.command


def test_both_installed_surfaces_delegate_target_provision_and_report_to_one_runtime(
    *, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = pathlib.Path(__file__).parents[1]
    module_path = root / "overseer" / "_lpm_commands.py"
    assert module_path.is_file(), "the shared manager command dispatcher must exist"
    commands = importlib.import_module("_lpm_commands")
    runtime = _RecordingRuntime()

    assert [
        commands.run_manager_command(arguments=(command, flag, "-"), runtime=runtime)
        for command, flag in (
            ("target", "--target-json"),
            ("provision", "--request-json"),
            ("report", "--report-json"),
        )
    ] == ["target", "provision", "report"]
    assert runtime.commands == ["target", "provision", "report"]

    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'llm-provider-manager = "overseer.manager_bootstrap:main"' in metadata
    launcher = root / ".claude-plugin" / "bin" / "llm-provider-manager"
    assert launcher.is_file()
    assert launcher.stat().st_mode & 0o111
    assert "overseer/manager_bootstrap.py" in launcher.read_text(encoding="utf-8")
    assert (root / ".claude-plugin" / "overseer" / "_lpm_commands.py").read_bytes() == (
        module_path.read_bytes()
    )

    bootstrap = importlib.import_module("manager_bootstrap")
    inherited = {
        "PATH": "/usr/bin",
        "ANTHROPIC_API_KEY": "must-not-be-read",
        "op_service_account_token": "must-not-be-read",
    }
    assert bootstrap.scrub_credential_overrides(environ=inherited) == (
        "ANTHROPIC_API_KEY",
        "op_service_account_token",
    )
    assert inherited == {"PATH": "/usr/bin"}

    invoked: list[tuple[str, ...]] = []

    def record_exec(_program: str, argv: list[str]) -> None:
        invoked.append(tuple(argv))

    monkeypatch.setattr(bootstrap, "execv", record_exec)
    monkeypatch.setattr(bootstrap.sys, "argv", ["llm-provider-manager", "target"])
    assert bootstrap.main() == 70
    assert invoked[0][1:3] == ("-I", "-S")
    assert capsys.readouterr().out.startswith('{"version":1,"status":"error"')

    monkeypatch.setattr(bootstrap.sys, "argv", ["llm-provider-manager", "--help"])
    assert bootstrap.main() == 0
    assert capsys.readouterr().out.startswith("usage: llm-provider-manager")
