"""Contract checks for the Claude-on-tmux isolated-exercise controller."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROLLER = REPO_ROOT / "scripts" / "overseer-live-exercise-claude-tmux.sh"
STUB = REPO_ROOT / "tests" / "stub_claude.py"
STUB_SHIM_PREPARER = REPO_ROOT / "scripts" / "overseer-live-exercise-stub-shims.sh"


def test_controller_is_checked_in_executable_and_uses_only_the_exercise_socket() -> None:
    """The controller is executable and centralizes tmux behind the private socket."""
    assert CONTROLLER.is_file(), "the Claude tmux controller is missing"
    assert os.access(CONTROLLER, os.X_OK), "the Claude tmux controller is not executable"
    source = CONTROLLER.read_text(encoding="utf-8")
    assert 'tmux -S "$endpoint"' in source
    assert "tmux " not in source.replace('tmux -S "$endpoint"', "")


def test_replacement_evidence_labels_both_process_identity_components() -> None:
    """A reviewer can read the predecessor and successor PID/start-time pairs."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "predecessor pid=" in source
    assert "successor pid=" in source
    assert "starttime=" in source


def test_controller_gives_a_stub_the_same_bootstrap_ancestry_and_scopes_successor() -> None:
    """The released bootstrap sees Claude ancestry and the daemon verifies replacement."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "CLAUDECODE=1" in source
    assert '"$(snapshot_row session_identity)" == "$successor"' in source


def test_controller_keeps_a_stable_pane_and_private_server_path_for_replacement() -> None:
    """Window renames and a late-added stub PATH cannot break the shipped relaunch."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "agent_target=\"$(tx new-window -d -P -F '#{pane_id}'" in source
    assert 'tx set-environment -g PATH "$PATH"' in source


def test_checked_in_claude_stub_and_launcher_are_available_for_the_private_tmux_run() -> None:
    """The proof uses tracked fixtures instead of writing an agent double under `/tmp`."""
    assert STUB.is_file(), "the idle-Claude fixture is missing"
    preparer = STUB_SHIM_PREPARER.read_text(encoding="utf-8")
    assert "--claude-script" in preparer
    assert '"$bin_dir/claude"' in preparer
