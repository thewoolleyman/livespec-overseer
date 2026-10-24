"""A multi-line paste that Claude collapses to a placeholder is still a landed paste.

Measured live 2026-10-12 against v5.25.0: the daemon bracketed-pasted a wrap-up into
a herdr-hosted Claude pane, Claude rendered it in the composer as
``[Pasted text #1 +41 lines]``, and because ``prompt_visible`` demanded the composer
equal the payload's FIRST LINE, the paste was judged never to have landed. Enter was
therefore never sent, the wrap-up sat unsubmitted, and the round was rolled back.
"""

from __future__ import annotations

from pathlib import Path

import pane_router_submit_signals
from test_supervisor_builders import idle_capture

__all__: list[str] = []

_WRAPUP = "You are down to 50% of your context.\nPlease start wrapping up.\n" + "line\n" * 40
_CODEX_01630_COMPOSER = (
    Path(__file__).parent / "fixtures" / "codex-composer" / "0.163.0-pasted-content.txt"
).read_text(encoding="utf-8")


def _composer(*, content: str) -> str:
    return idle_capture(ctx=50).replace("\n❯ \n", f"\n❯ {content}\n")


def test_a_collapsed_multi_line_paste_is_visible() -> None:
    capture = _composer(content="[Pasted text #1 +41 lines]")
    assert pane_router_submit_signals.prompt_visible(capture=capture, text=_WRAPUP) is True


def test_a_collapsed_paste_after_a_numbered_history_is_visible() -> None:
    capture = _composer(content="[Pasted text #3 +41 lines]")
    assert pane_router_submit_signals.prompt_visible(capture=capture, text=_WRAPUP) is True


def test_the_payload_first_line_is_still_visible() -> None:
    capture = _composer(content="You are down to 50% of your context.")
    assert pane_router_submit_signals.prompt_visible(capture=capture, text=_WRAPUP) is True


def test_unrelated_composer_text_is_not_our_paste() -> None:
    capture = _composer(content="half-typed operator note")
    assert pane_router_submit_signals.prompt_visible(capture=capture, text=_WRAPUP) is False


def test_a_placeholder_does_not_stand_in_for_a_single_line_payload() -> None:
    capture = _composer(content="[Pasted text #1 +41 lines]")
    assert (
        pane_router_submit_signals.prompt_visible(capture=capture, text="Continue the plan.")
        is False
    )


def test_a_codex_collapsed_multi_line_paste_is_visible() -> None:
    assert (
        pane_router_submit_signals.prompt_visible(capture=_CODEX_01630_COMPOSER, text=_WRAPUP)
        is True
    )


def test_a_codex_placeholder_does_not_stand_in_for_a_single_line_payload() -> None:
    assert (
        pane_router_submit_signals.prompt_visible(
            capture=_CODEX_01630_COMPOSER, text="Continue the plan."
        )
        is False
    )


def test_a_codex_composer_showing_the_payload_first_line_is_visible() -> None:
    capture = (
        "› You are down to 50% of your context.\n  gpt-5.5 high · /x/repo · Context 50% left\n"
    )
    assert pane_router_submit_signals.prompt_visible(capture=capture, text=_WRAPUP) is True
