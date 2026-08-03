"""Guards for release-tier dynamic LLOC decompositions."""

from __future__ import annotations

import importlib
from pathlib import Path


def test_claude_sessions_concerns_are_split_from_facade() -> None:
    root = Path(__file__).resolve().parents[1]
    expected_modules = [
        "_claude_sessions_proc",
        "_claude_sessions_registry",
        "_claude_sessions_subshell",
        "_claude_sessions_tmux",
    ]
    for module_name in expected_modules:
        assert (root / "overseer" / f"{module_name}.py").is_file()
        importlib.import_module(module_name)

    facade = importlib.import_module("claude_sessions")
    private_names = {
        "_proc_stat_fields",
        "_runtime_starttime_ticks",
        "_starttime_ticks",
    }
    assert private_names.isdisjoint(vars(facade))


def test_release_tier_test_modules_are_split_by_concern() -> None:
    root = Path(__file__).resolve().parents[1]
    expected_modules = [
        "test_claude_sessions_proc",
        "test_claude_sessions_registry",
        "test_claude_sessions_subshell",
        "test_supervisor_background_restart_live",
    ]
    for module_name in expected_modules:
        assert (root / "overseer" / f"{module_name}.py").is_file()
