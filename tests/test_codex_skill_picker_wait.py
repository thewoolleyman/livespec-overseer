"""Unit coverage for the Codex skill-picker wait helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_HELPER_PATH = Path(__file__).with_name("e2e_cli_picker.py")


def _picker_helpers():
    assert _HELPER_PATH.is_file()
    spec = importlib.util.spec_from_file_location("e2e_cli_picker", _HELPER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_mentions_list_redrawn_at_an_earlier_screen_offset_opens_the_picker() -> None:
    helpers = _picker_helpers()
    before = "\n".join("x" * 100 for _ in range(39))
    after = "Mentions\noverseer (livespec-overseer)  Skill"

    assert helpers.picker_has_new_marker(
        before=before,
        after=after,
        markers=("Mentions", "overseer (livespec-overseer)"),
    )
