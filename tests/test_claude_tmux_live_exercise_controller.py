"""Contract checks for the Claude-on-tmux isolated-exercise controller."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROLLER = REPO_ROOT / "scripts" / "overseer-live-exercise-claude-tmux.sh"


def test_controller_is_checked_in_executable_and_uses_only_the_exercise_socket() -> None:
    """The controller is executable and centralizes tmux behind the private socket."""
    assert CONTROLLER.is_file(), "the Claude tmux controller is missing"
    assert os.access(CONTROLLER, os.X_OK), "the Claude tmux controller is not executable"
    source = CONTROLLER.read_text(encoding="utf-8")
    assert 'tmux -S "$endpoint"' in source
    assert "tmux " not in source.replace('tmux -S "$endpoint"', "")
