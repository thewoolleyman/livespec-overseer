"""Tests for caam model-picker driving."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import tmuxio
from test_tmuxio_fakes import io as _io

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PICKER_MODULE = ROOT / "overseer" / "caam_picker.py"


def picker_module() -> ModuleType:
    assert PICKER_MODULE.is_file()
    return importlib.import_module("caam_picker")


class FakePickerTmux:
    def __init__(self, *, captures: tuple[str, ...]) -> None:
        self._captures = list(captures)
        self.keys: list[str] = []

    def capture_pane(self, *, session: str) -> str:
        _ = session
        if not self._captures:
            return ""
        return self._captures.pop(0)

    def send_keys(self, *, session: str, keys: str) -> bool:
        _ = session
        self.keys.append(keys)
        return True

    def send_literal_keys(self, *, session: str, text: str) -> bool:
        _ = session
        self.keys.append(text)
        return True


class SleepLog:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def test_tmuxio_literal_keys_use_the_literal_send_keys_form() -> None:
    io, fake = _io()
    assert io.send_literal_keys(session="s", text="/model") is True
    assert fake.calls[0]["argv"] == ["tmux", "send-keys", "-l", "-t", "s", "/model"]


def test_picker_driver_uses_absolute_tmux_path() -> None:
    caam_picker = picker_module()
    driver = caam_picker.real_picker_tmux()
    assert isinstance(driver, tmuxio.TmuxIO)
    assert driver.tmux_binary() == "/usr/bin/tmux"


def test_pane_is_idle_admits_only_an_empty_prompt() -> None:
    caam_picker = picker_module()
    assert caam_picker.pane_is_idle(screen="older\n\n❯\n") is True
    assert caam_picker.pane_is_idle(screen="older\n❯ /model\n") is False
    assert caam_picker.pane_is_idle(screen="older\nno prompt\n") is False


def test_picker_rows_are_scoped_after_last_header() -> None:
    caam_picker = picker_module()
    screen = """
Earlier conversation:
1. Haiku
2. Fable

Select model
  1. Default     Opus 5
❯ 2. Fable      Fast model
  3. Opus       Larger model
"""
    rows = caam_picker.picker_rows(screen=screen, header="Select model")
    assert tuple(row.text for row in rows) == (
        "Default     Opus 5",
        "Fable      Fast model",
        "Opus       Larger model",
    )
    assert caam_picker.highlighted_row_number(screen=screen, header="Select model") == 2


def test_row_matching_is_by_name_and_label_first() -> None:
    caam_picker = picker_module()
    rows = (
        caam_picker.PickerRow(number=1, text="Default     Opus 5 with 1M context"),
        caam_picker.PickerRow(number=2, text="Opus       Primary model"),
    )
    assert caam_picker.row_for_model(rows=rows, want="opus") == rows[1]


def test_drive_picker_wraps_downward_to_target_above_highlight() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(
        captures=(
            "❯\n",
            """
Select model
❯ 1. Fable      Fast model
  2. Haiku      Small model
  3. Opus       Larger model
""",
            "❯\n",
        )
    )
    sleep = SleepLog()

    caam_picker.drive_model_picker(
        tmux=tmux,
        session="s",
        want="opus",
        sleep=sleep,
    )

    assert tmux.keys == ["/model", "Enter", "Down", "Down", "s"]
    assert sleep.calls == [0.4, 1.5, 0.3, 1.2]


def test_absent_wanted_model_dismisses_picker() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(
        captures=(
            "❯\n",
            """
Select model
❯ 1. Fable      Fast model
  2. Haiku      Small model
""",
        )
    )

    caam_picker.drive_model_picker(
        tmux=tmux,
        session="s",
        want="opus",
        sleep=SleepLog(),
    )

    assert tmux.keys == ["/model", "Enter", "Escape"]


def test_second_confirmation_dialog_is_answered_by_name() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(
        captures=(
            "❯\n",
            """
Select model
❯ 1. Fable      Fast model
  2. Opus       Larger model
""",
            """
Switch model?
❯ 1. No
  2. Yes
""",
        )
    )
    sleep = SleepLog()

    caam_picker.drive_model_picker(
        tmux=tmux,
        session="s",
        want="opus",
        sleep=sleep,
    )

    assert tmux.keys == ["/model", "Enter", "Down", "s", "Down", "Enter"]
    assert sleep.calls == [0.4, 1.5, 0.3, 1.2, 0.2]


def test_half_typed_prompt_is_skipped_without_opening_picker() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(captures=("❯ half typed\n",))

    caam_picker.drive_model_picker(
        tmux=tmux,
        session="s",
        want="opus",
        sleep=SleepLog(),
    )

    assert tmux.keys == []


def test_emitted_keys_contain_no_horizontal_or_jump_keys() -> None:
    caam_picker = picker_module()
    tmux = FakePickerTmux(
        captures=(
            "❯\n",
            """
Select model
❯ 1. Fable      Fast model
  2. Opus       Larger model
""",
            """
Switch model?
❯ 1. No
  2. Yes
""",
        )
    )

    caam_picker.drive_model_picker(
        tmux=tmux,
        session="s",
        want="opus",
        sleep=SleepLog(),
    )

    assert tmux.keys == ["/model", "Enter", "Down", "s", "Down", "Enter"]
    assert set(tmux.keys).isdisjoint({"Left", "Right", "Home", "End", "PageUp", "PageDown"})
