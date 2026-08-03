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


def test_cli_wiring_fixed_remaining_edges_are_split_from_read_only_list() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "overseer" / "test_supervisor_cli_wiring_fixed.py"
    target = root / "overseer" / "test_supervisor_remaining_single_branch.py"
    moved_tests = [
        "test_live_outside_tmux_note_omits_the_suffix_when_no_status_is_reported",
        "test_failed_paste_in_an_already_open_round_keeps_the_rounds_stamp",
    ]

    assert target.is_file()
    source_text = source.read_text()
    target_text = target.read_text()
    for test_name in moved_tests:
        assert f"def {test_name}" in target_text
        assert f"def {test_name}" not in source_text
