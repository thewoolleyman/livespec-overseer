"""The installed zero-argument manager returns its typed attention view."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_SUPPORT = _ROOT / "overseer" / "test_lpm_installed_sandbox.py"
_RECORD_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"


def _support() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lpm_installed_attention_sandbox", _SUPPORT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zero_argument_installed_executable_returns_one_typed_attention_result(
    tmp_path: Path,
) -> None:
    sandbox = _support().InstalledManagerSandbox.create(root=tmp_path, repository=_ROOT)
    assert hasattr(sandbox, "write_attention"), "the sandbox must seed installed attention state"
    path = sandbox.write_attention(record_id=_RECORD_ID)

    result = sandbox.run(surface="plugin", arguments=())

    assert result.exit_status == 0
    assert result.stderr == ""
    assert result.body == {
        "version": 1,
        "status": "ok",
        "operation": "attention",
        "items": [
            {
                "path": path,
                "record_id": _RECORD_ID,
                "provider": "anthropic",
                "account_id": "fixture-anthropic-account",
                "reason": "captcha",
                "deadline": "2026-10-11T18:00:00Z",
            }
        ],
    }
