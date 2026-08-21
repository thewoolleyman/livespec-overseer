"""Model-picker driving for caam account rotation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Protocol

import tmuxio

__all__: list[str] = [
    "PickerRow",
    "drive_model_picker",
    "highlighted_row_number",
    "pane_is_idle",
    "picker_rows",
    "real_picker_tmux",
    "row_for_model",
]

_REAL_TMUX: Final = "/usr/bin/tmux"
_MODEL_HEADER: Final = "Select model"
_SWITCH_HEADER: Final = "Switch model?"
_PROMPT_PREFIX: Final = "❯"
_IDLE_SCAN_LINES: Final = 6
_ROW_RE: Final = re.compile(r"^[^0-9\n]*?(\d+)\.\s+(\S.*)$", re.MULTILINE)
_HIGHLIGHT_RE: Final = re.compile(r"❯\s*(\d+)\.")
_YES_RE: Final = re.compile(r"^Yes\b", re.IGNORECASE)


@dataclass(frozen=True, kw_only=True)
class PickerRow:
    number: int
    text: str


class PickerTmux(Protocol):
    def capture_pane(self, *, session: str) -> str: ...

    def send_keys(self, *, session: str, keys: str) -> bool: ...

    def send_literal_keys(self, *, session: str, text: str) -> bool: ...


class Sleep(Protocol):
    def __call__(self, seconds: float) -> None: ...


def real_picker_tmux() -> tmuxio.TmuxIO:
    return tmuxio.TmuxIO(tmux_bin=_REAL_TMUX)


def pane_is_idle(*, screen: str) -> bool:
    lines = [line.strip() for line in screen.splitlines() if line.strip()]
    for line in reversed(lines[-_IDLE_SCAN_LINES:]):
        if line.startswith(_PROMPT_PREFIX):
            return line == _PROMPT_PREFIX
    return False


def picker_rows(*, screen: str, header: str) -> tuple[PickerRow, ...]:
    post_header = _post_header(screen=screen, header=header)
    return tuple(
        PickerRow(number=int(match.group(1)), text=match.group(2))
        for match in _ROW_RE.finditer(post_header)
    )


def highlighted_row_number(*, screen: str, header: str) -> int | None:
    match = _HIGHLIGHT_RE.search(_post_header(screen=screen, header=header))
    if match is None:
        return None
    return int(match.group(1))


def row_for_model(*, rows: tuple[PickerRow, ...], want: str) -> PickerRow | None:
    wanted = re.compile(rf"\b{re.escape(want)}\b", re.IGNORECASE)
    label_match = next((row for row in rows if wanted.search(_row_label(row=row))), None)
    anywhere_match = next((row for row in rows if wanted.search(row.text)), None)
    return label_match if label_match is not None else anywhere_match


def drive_model_picker(*, tmux: PickerTmux, session: str, want: str, sleep: Sleep) -> None:
    if not pane_is_idle(screen=tmux.capture_pane(session=session)):
        return

    _ = tmux.send_literal_keys(session=session, text="/model")
    sleep(0.4)
    _ = tmux.send_keys(session=session, keys="Enter")
    sleep(1.5)

    screen = tmux.capture_pane(session=session)
    rows = picker_rows(screen=screen, header=_MODEL_HEADER)
    here = highlighted_row_number(screen=screen, header=_MODEL_HEADER)
    target = row_for_model(rows=rows, want=want)
    if here is None or target is None:
        _ = tmux.send_keys(session=session, keys="Escape")
        return

    _move_down(tmux=tmux, session=session, count=(target.number - here) % len(rows))
    sleep(0.3)
    _ = tmux.send_literal_keys(session=session, text="s")
    sleep(1.2)

    screen = tmux.capture_pane(session=session)
    _answer_switch_dialog(tmux=tmux, session=session, screen=screen, sleep=sleep)


def _answer_switch_dialog(*, tmux: PickerTmux, session: str, screen: str, sleep: Sleep) -> None:
    rows = picker_rows(screen=screen, header=_SWITCH_HEADER)
    here = highlighted_row_number(screen=screen, header=_SWITCH_HEADER)
    target = _yes_row(rows=rows)
    if here is None or target is None:
        return
    _move_down(tmux=tmux, session=session, count=(target.number - here) % len(rows))
    sleep(0.2)
    _ = tmux.send_keys(session=session, keys="Enter")


def _post_header(*, screen: str, header: str) -> str:
    index = screen.rfind(header)
    if index < 0:
        return ""
    return screen[index + len(header) :]


def _row_label(*, row: PickerRow) -> str:
    return re.split(r"\s{2,}", row.text, maxsplit=1)[0]


def _yes_row(*, rows: tuple[PickerRow, ...]) -> PickerRow | None:
    for row in rows:
        if _YES_RE.search(_row_label(row=row)):
            return row
    return None


def _move_down(*, tmux: PickerTmux, session: str, count: int) -> None:
    for _ in range(count):
        _ = tmux.send_keys(session=session, keys="Down")
