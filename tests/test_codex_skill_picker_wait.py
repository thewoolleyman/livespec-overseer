"""Unit coverage for the Codex skill-picker wait helpers."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

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


def test_a_redrawn_mentions_list_opens_even_when_its_header_was_already_visible(
    monkeypatch,
) -> None:
    helpers = _picker_helpers()
    transcript = "Mentions\n  livespec-overseer  Plugin"
    redrawn = helpers._plain(text="Mentions\n  overseer  Dir")
    expected_row = "overseer (livespec-overseer)"

    def read_until(**kwargs: object) -> str:
        predicate = kwargs["predicate"]
        assert callable(predicate)
        if kwargs["phase"] == "picker open":
            assert predicate(redrawn)
            return redrawn
        rendered_row = f"{redrawn}\n{expected_row}  Skill"
        assert predicate(rendered_row)
        return rendered_row

    monkeypatch.setattr(helpers, "_send", lambda **_: None)
    monkeypatch.setattr(helpers, "_read_until", read_until)

    current = helpers._open_skills_list(
        exercise=helpers._Exercise(fd=1),
        transcript=transcript,
        query="livespec-overseer:overseer",
        expected_row=expected_row,
    )

    assert current.endswith("Skill")


def test_an_unchanged_mentions_list_does_not_open_the_picker(monkeypatch) -> None:
    helpers = _picker_helpers()
    transcript = "Mentions\n  livespec-overseer  Plugin"
    before = helpers._plain(text=transcript)

    class StopAfterOpeningCheckError(Exception):
        pass

    def read_until(**kwargs: object) -> str:
        predicate = kwargs["predicate"]
        assert callable(predicate)
        assert kwargs["phase"] == "picker open"
        assert not predicate(before)
        raise StopAfterOpeningCheckError

    monkeypatch.setattr(helpers, "_send", lambda **_: None)
    monkeypatch.setattr(helpers, "_read_until", read_until)

    with pytest.raises(StopAfterOpeningCheckError):
        _ = helpers._open_skills_list(
            exercise=helpers._Exercise(fd=1),
            transcript=transcript,
            query="livespec-overseer:overseer",
            expected_row="overseer (livespec-overseer)",
        )


def test_the_picker_filters_on_the_declared_plugin_and_skill(monkeypatch) -> None:
    helpers = _picker_helpers()
    opened: dict[str, object] = {}
    monkeypatch.setattr(helpers, "_send", lambda **_: None)
    monkeypatch.setattr(helpers, "_await_codex_prompt", lambda **_: "prompt")
    monkeypatch.setattr(
        helpers,
        "_open_skills_list",
        lambda **kwargs: opened.update(kwargs) or "picker transcript",
    )

    assert (
        helpers._exercise_skills_picker(
            master_fd=1,
            plugin="livespec-overseer",
            skill="overseer",
        )
        == "picker transcript"
    )
    assert opened["query"] == "livespec-overseer:overseer"
