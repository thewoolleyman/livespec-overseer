"""Tests for the always-loaded instruction surface budget gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "check-instruction-surface-budget.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("instruction_surface_budget", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_instruction_surface_budget_counts_utf8_characters_not_bytes(tmp_path: Path) -> None:
    module = _load_module()
    agents = tmp_path / "AGENTS.md"
    _ = agents.write_text("abcé\n", encoding="utf-8")
    claude = tmp_path / "CLAUDE.md"
    claude.symlink_to(agents)

    report = module.measure_instruction_surface(root=tmp_path, budget=10)

    assert report.current_chars == 5
    assert agents.read_bytes().__len__() == 6
    assert report.headroom == 5


def test_instruction_surface_budget_deduplicates_symlinked_surface(tmp_path: Path) -> None:
    module = _load_module()
    agents = tmp_path / "AGENTS.md"
    _ = agents.write_text("abcd", encoding="utf-8")
    claude = tmp_path / "CLAUDE.md"
    claude.symlink_to(agents)

    report = module.measure_instruction_surface(root=tmp_path, budget=5)

    assert report.current_chars == 4
    assert report.paths == (agents,)


def test_instruction_surface_budget_fails_over_budget_with_actionable_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    agents = tmp_path / "AGENTS.md"
    _ = agents.write_text("abcdef", encoding="utf-8")

    return_code = module.main(argv=["--root", str(tmp_path), "--budget", "5", "--enforce"])
    captured = capsys.readouterr()

    assert return_code == 1
    assert "current=6 chars" in captured.err
    assert "budget=5 chars" in captured.err
    assert "overflow=1 chars" in captured.err


def test_instruction_surface_budget_passes_under_budget_with_headroom(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    agents = tmp_path / "AGENTS.md"
    _ = agents.write_text("abcd", encoding="utf-8")

    return_code = module.main(argv=["--root", str(tmp_path), "--budget", "5"])
    captured = capsys.readouterr()

    assert return_code == 0
    assert "current=4 chars" in captured.out
    assert "budget=5 chars" in captured.out
    assert "headroom=1 chars" in captured.out


def test_instruction_surface_budget_is_reached_by_full_check() -> None:
    justfile = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")

    assert "check-instruction-surface-budget" in justfile
