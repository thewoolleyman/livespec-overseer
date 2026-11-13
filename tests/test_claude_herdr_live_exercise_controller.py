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
