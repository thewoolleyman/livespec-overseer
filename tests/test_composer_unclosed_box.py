"""A bordered prompt row with no closing border is not a composer.

The multi-row composer reader collects continuation rows up to the closing border;
when the capture ends (or the row cap is reached) before one appears, what it saw
was not a whole composer box, so it must report no composer text at all.
"""

from __future__ import annotations

import signals

__all__: list[str] = []

_RULE = "─" * 40


def test_a_composer_cut_off_before_its_closing_border_is_not_read() -> None:
    capture = f"{_RULE}\n❯ resume plan epic\n  ledger-held plan state\n"
    assert signals.input_box_text(capture_text=capture) is None


def test_continuation_rows_past_the_cap_are_not_a_composer() -> None:
    rows = "\n".join(f"  row {index}" for index in range(80))
    capture = f"{_RULE}\n❯ start\n{rows}\n{_RULE}\n"
    assert signals.input_box_text(capture_text=capture) is None
