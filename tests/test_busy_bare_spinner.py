"""A Claude turn is busy from its first spinner frame, not only once counters appear.

Measured 2026-10-12 against Claude Code 2.1.296 in a herdr pane, sampling every 0.2 s
after Enter: for the first ~2.2 s the only activity line is a bare spinner such as
``✽ Hatching…`` (glyph, word, ellipsis), then ``(2s · thinking)``, and only at ~3 s a
token counter. The daemon confirms a submit by watching for busy within 1.5 s, so a
real, delivered turn never read as busy and every wrap-up was judged undelivered.
"""

from __future__ import annotations

import pytest
import signals

__all__: list[str] = []

_PROMPT = "❯ Count slowly from 1 to 30, one number per line."
_COMPOSER = "─" * 40 + "\n❯ \n" + "─" * 40


@pytest.mark.parametrize(
    "spinner",
    [
        "✽ Hatching…",
        "✶ Hatching…",
        "· Hatching…",
        "* Hatching…",
        "✶ Flibbertigibbeting… (2s · thinking)",
    ],
)
def test_the_first_spinner_frames_of_a_turn_are_busy(*, spinner: str) -> None:
    capture = f"{_PROMPT}\n\n{spinner}\n\n{_COMPOSER}\n"
    assert signals.is_busy(capture_text=capture) is True


def test_a_completed_turn_summary_is_still_not_busy() -> None:
    capture = f"{_PROMPT}\n● done\n\n✻ Baked for 17s\n\n{_COMPOSER}\n"
    assert signals.is_busy(capture_text=capture) is False
