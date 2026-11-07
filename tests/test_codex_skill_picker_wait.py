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
    monkeypatch: pytest.MonkeyPatch,
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helpers = _picker_helpers()
    read_fd, write_fd = os.pipe()
    expected_row = "overseer (livespec-overseer)"
    sent: list[str] = []

    def send_frames(*, fd: int, text: str) -> None:
        sent.append(text)
        if len(sent) == 1:
            os.write(
                write_fd,
                b"\x1b[2J\x1b[1;1HMentions\x1b[2;1Hoverseer ./  Dir"
                b"\x1b[3;1HREADME.md  File\x1b[4;1H\xe2\x86\x93",
            )
        else:
            os.write(
                write_fd,
                ("\x1b[2J\x1b[1;1HMentions" f"\x1b[2;1H{expected_row}  Skill").encode(),
            )

    try:
        monkeypatch.setattr(helpers, "_send", send_frames)
        monkeypatch.setattr(helpers, "_CODEX_PICKER_STALL_SECONDS", 0.5)
        current = helpers._open_skills_list(
            exercise=helpers._Exercise(fd=read_fd),
            transcript="\x1b[2J\x1b[1;1HMentions\x1b[2;1Hlivespec-overseer  Plugin",
            query="overseer",
            expected_row=expected_row,
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert sent == ["\x15@overseer", "\x1b[B"]
    assert f"{expected_row}  Skill" in helpers._plain(text=current)


def test_an_unchanged_mentions_list_does_not_open_the_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helpers = _picker_helpers()
    transcript = "Mentions\nlivespec-overseer  Plugin"
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
            query="overseer",
            expected_row="overseer (livespec-overseer)",
        )


def test_an_unrelated_redraw_does_not_open_an_existing_mentions_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helpers = _picker_helpers()
    transcript = "Mentions\nlivespec-overseer  Plugin\n› Ask Codex to do anything"
    unrelated_redraw = "Mentions\nlivespec-overseer  Plugin\n› Loading model…"
    redrawn = helpers._plain(text=unrelated_redraw)

    class StopAfterOpeningCheckError(Exception):
        pass

    def read_until(**kwargs: object) -> str:
        predicate = kwargs["predicate"]
        assert callable(predicate)
        assert kwargs["phase"] == "picker open"
        assert not predicate(redrawn)
        raise StopAfterOpeningCheckError

    monkeypatch.setattr(helpers, "_send", lambda **_: None)
    monkeypatch.setattr(helpers, "_read_until", read_until)

    with pytest.raises(StopAfterOpeningCheckError):
        _ = helpers._open_skills_list(
            exercise=helpers._Exercise(fd=1),
            transcript=transcript,
            query="overseer",
            expected_row="overseer (livespec-overseer)",
        )


def test_the_picker_scrolls_until_the_skill_row_is_drawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helpers = _picker_helpers()
    read_fd, write_fd = os.pipe()
    sent: list[str] = []
    expected_row = "overseer (livespec-overseer)"

    def send_picker_frame(*, fd: int, text: str) -> None:
        sent.append(text)
        if len(sent) == 1:
            os.write(
                write_fd,
                b"\x1b[2J\x1b[1;1HMentions\x1b[2;1Hlivespec-overseer  Plugin"
                b"\x1b[3;1Hoverseer ./  Dir\x1b[4;1HREADME.md  File\x1b[5;1H\xe2\x86\x93",
            )
        elif text == "\x1b[B":
            os.write(
                write_fd,
                ("\x1b[2J\x1b[1;1HMentions" f"\x1b[2;1H{expected_row}  Skill").encode(),
            )

    try:
        monkeypatch.setattr(helpers, "_send", send_picker_frame)
        monkeypatch.setattr(helpers, "_CODEX_PICKER_STALL_SECONDS", 0.05)
        current = helpers._open_skills_list(
            exercise=helpers._Exercise(fd=read_fd),
            transcript="› Ask Codex to do anything",
            query="overseer",
            expected_row=expected_row,
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert sent == ["\x15@overseer", "\x1b[B"]
    assert f"{expected_row}  Skill" in helpers._plain(text=current)


def test_an_expected_row_without_a_mentions_list_does_not_open_the_picker() -> None:
    helpers = _picker_helpers()
    expected_row = "overseer (livespec-overseer)"

    assert not helpers._mentions_list_is_new(
        before="› Ask Codex to do anything",
        plain=f"› Ask Codex to do anything\n{expected_row} Skill is mentioned in a banner",
        expected_row=expected_row,
    )


def test_the_picker_moves_once_per_redraw_and_not_during_silent_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helpers = _picker_helpers()
    read_fd, write_fd = os.pipe()
    sent: list[str] = []

    def send_one_unrelated_redraw(*, fd: int, text: str) -> None:
        sent.append(text)
        if len(sent) == 1:
            os.write(
                write_fd,
                b"\x1b[2J\x1b[1;1HMentions\x1b[2;1Hlivespec-overseer  Plugin",
            )

    try:
        monkeypatch.setattr(helpers, "_send", send_one_unrelated_redraw)
        monkeypatch.setattr(helpers, "_CODEX_PICKER_STALL_SECONDS", 0.6)
        with pytest.raises(AssertionError, match="picker render wait expired"):
            _ = helpers._open_skills_list(
                exercise=helpers._Exercise(fd=read_fd),
                transcript="› Ask Codex to do anything",
                query="overseer",
                expected_row="overseer (livespec-overseer)",
            )
    finally:
        os.close(read_fd)
        os.close(write_fd)

    assert sent == ["\x15@overseer", "\x1b[B"]
