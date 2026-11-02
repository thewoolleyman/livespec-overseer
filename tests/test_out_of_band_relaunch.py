"""The sanctioned operator relaunch is a separate, non-destructive surface."""

from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "overseer" / "out_of_band_relaunch.py"


def test_sanctioned_relaunch_entrypoint_is_a_separate_operator_surface() -> None:
    """A relaunch cannot use `start`, whose respawn path is allowed to terminate."""
    assert MODULE_PATH.is_file()
    entrypoint = importlib.import_module("out_of_band_relaunch")
    assert callable(entrypoint.relaunch)
