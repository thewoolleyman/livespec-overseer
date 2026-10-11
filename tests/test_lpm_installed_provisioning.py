"""Installed manager subprocesses exercise the real credential-provider boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_SUPPORT = _ROOT / "overseer" / "test_lpm_installed_sandbox.py"


def _support() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lpm_installed_sandbox", _SUPPORT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_install_exposes_console_and_absolute_plugin_executable(tmp_path: Path) -> None:
    assert _SUPPORT.is_file(), "the installed subprocess sandbox must exist"
    sandbox = _support().InstalledManagerSandbox.create(root=tmp_path, repository=_ROOT)

    assert sandbox.console_on_path() == "/opt/lpm/bin/llm-provider-manager"
    result = sandbox.run(
        surface="plugin",
        arguments=("target", "--target-json", "-"),
        input_text="{}",
    )

    assert result.executable == "/plugin/bin/llm-provider-manager"
    assert result.exit_status == 2
    assert result.body["error_type"] == "invalid-request"
