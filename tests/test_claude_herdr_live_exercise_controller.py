"""Contract checks for the Claude-on-Herdr live-exercise controller."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROLLER = ROOT / "scripts" / "overseer-live-exercise-claude-herdr.sh"


def test_the_claude_controller_is_checked_in_and_executable() -> None:
    """The host exercise has a directly runnable, executable Claude controller."""
    assert CONTROLLER.is_file(), f"the controller is missing from the repository: {CONTROLLER}"
    assert os.access(CONTROLLER, os.X_OK), f"the controller is not executable: {CONTROLLER}"


def test_replacement_requires_the_successor_to_remain_in_the_adopted_pane() -> None:
    """A new process elsewhere is not a retained-pane replacement."""
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'tracked_pane="$(snapshot_row tmux)"' in controller
    assert '[[ "$(snapshot_row tmux)" == "$tracked_pane" ]]' in controller
