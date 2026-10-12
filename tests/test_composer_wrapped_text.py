"""A prompt that wraps across composer rows is still the composer's text.

Reproduced on 2026-10-12 in the isolated live exercise: after a ready restart the
daemon pasted its one-line resume prompt into the successor Claude, which wrapped it
onto two composer rows. The composer reader required a border directly below the
``❯`` row, so it saw no prompt at all; the daemon never pressed Enter and every retry
refused with "pending resume text is absent, gated, or differs".
"""

from __future__ import annotations

import pane_router_submit_signals
import signals

__all__: list[str] = []

_RESUME = (
    "resume plan epic overseer-exercise-scratch-epic in repository "
    "/tmp/livespec-overseer-exercise-repo; read its ledger-held plan state"
)
_RULE = "─" * 100
_WRAPPED = (
    f"\n{_RULE}\n"
    "❯ resume plan epic overseer-exercise-scratch-epic in repository "
    "/tmp/livespec-overseer-exercise-repo; read its\n"
    "  ledger-held plan state\n"
    f"{_RULE}\n"
    "  Ctx: 95% left\n"
)


def test_a_wrapped_composer_reads_as_its_whole_line() -> None:
    assert signals.input_box_text(capture_text=_WRAPPED) == _RESUME


def test_a_wrapped_resume_prompt_is_visible() -> None:
    assert pane_router_submit_signals.prompt_visible(capture=_WRAPPED, text=_RESUME) is True


def test_a_single_row_composer_is_unchanged() -> None:
    capture = f"\n{_RULE}\n❯ Continue the plan.\n{_RULE}\n"
    assert signals.input_box_text(capture_text=capture) == "Continue the plan."


def test_an_unbordered_prompt_row_is_still_not_a_composer() -> None:
    capture = "● answer\n❯ resume plan epic\n  ledger-held plan state\n"
    assert signals.input_box_text(capture_text=capture) is None
