"""Regression coverage for the foreman-panel reviewer execution split."""

from __future__ import annotations

import importlib
from pathlib import Path

import foreman_panel

__all__: list[str] = []


def test_reviewer_execution_is_extracted_to_cohesive_module():
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "foreman_panel_reviewers.py"

    assert module_path.is_file(), module_path
    module = importlib.import_module("foreman_panel_reviewers")
    assert module.__all__ == [
        "default_reviewer_command",
        "reviewer_argv",
        "reviewer_responses",
        "run_reviewer",
    ]
    assert foreman_panel.run_reviewer is module.run_reviewer
    source = Path(foreman_panel.__file__).read_text(encoding="utf-8")
    assert "def run_reviewer" not in source
