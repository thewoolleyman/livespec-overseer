"""Unit coverage for the Codex skill-picker wait helpers."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

_HELPER_PATH = Path(__file__).parent / "e2e-cli" / "test_codex_skill_picker.py"


def _picker_helpers() -> ModuleType:
    assert _HELPER_PATH.is_file()
    spec = importlib.util.spec_from_file_location("e2e_cli_picker", _HELPER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_a_mentions_list_redrawn_at_an_earlier_screen_offset_opens_the_picker(
    monkeypatch,
) -> None:
    helpers = _picker_helpers()
    read_fd, write_fd = os.pipe()
    try:
        transcript = "\x1b[2J" + "".join(f"\x1b[{row};1H{'x' * 100}" for row in range(1, 40))
        expected_row = "overseer (livespec-overseer)"
        os.write(
            write_fd,
            ("\x1b[2J\x1b[1;1HMentions" f"\x1b[2;1H{expected_row}  Skill").encode(),
        )
        monkeypatch.setattr(helpers, "_send", lambda **_: None)
        monkeypatch.setattr(helpers, "_CODEX_PICKER_STALL_SECONDS", 0.05)
        current = helpers._open_skills_list(
            exercise=helpers._Exercise(fd=read_fd),
            transcript=transcript,
            query="overseer",
            expected_row=expected_row,
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)

    plain = helpers._plain(text=current)
    assert "Mentions" in plain
    assert f"{expected_row}  Skill" in plain
