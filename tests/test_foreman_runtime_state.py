"""Tests for foreman_runtime_state.py fail-soft JSON loading."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []


def module():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_runtime_state")


def test_read_json_object_treats_malformed_and_non_object_json_as_empty(*, tmp_path: Path):
    state = module()
    path = tmp_path / "state.json"

    path.write_text("{oops}\n", encoding="utf-8")
    assert state.read_json_object(path=path) == {}

    path.write_text("[]\n", encoding="utf-8")
    assert state.read_json_object(path=path) == {}
