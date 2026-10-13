"""An idle Claude composer showing a dim prompt suggestion is still an idle composer.

Measured 2026-10-13 on the live fleet (Claude Code 2.1.296 in herdr): after a turn,
Claude renders a generated suggestion in the empty composer as dim ghost text, e.g.
``❯\\xa0\\x1b[0m\\x1b[2mcontinue\\x1b[0m``. Only the ``Try "..."`` placeholder was
recognised, so every such pane read as "not idle, busy, or gated" and sat in
``settling`` forever: no wrap-up was delivered, and a session that had declared
``ready`` was never restarted (its declaration expired after 30 minutes).
Undimmed text in the same position is typed input and must stay non-idle.
"""

from __future__ import annotations

import signals

__all__: list[str] = []

_RULE = "─" * 60
_STATUS = "  Opus 5.5 | /data/projects/livespec-overseer | master | Ctx: 41% left"


def _pane(*, composer: str) -> str:
    return f"● done\n\n✻ Worked for 9s\n\n{_RULE}\n{composer}\n{_RULE}\n{_STATUS}\n"


def test_a_dim_generated_suggestion_is_an_idle_composer() -> None:
    capture = _pane(composer="❯\xa0\x1b[0m\x1b[2mcontinue\x1b[0m")
    assert signals.is_idle_input(capture_text=capture) is True


def test_a_longer_dim_suggestion_is_an_idle_composer() -> None:
    capture = _pane(composer="❯\xa0\x1b[0m\x1b[2mkeep going with the plan\x1b[0m")
    assert signals.is_idle_input(capture_text=capture) is True


def test_undimmed_text_in_the_composer_is_typed_input_not_idle() -> None:
    capture = _pane(composer="❯\xa0Implement the work item livespec-dev-tooling-xpeeku")
    assert signals.is_idle_input(capture_text=capture) is False


def test_typed_text_followed_by_a_dim_tail_is_not_idle() -> None:
    capture = _pane(composer="❯\xa0fix\x1b[2m the tests\x1b[0m")
    assert signals.is_idle_input(capture_text=capture) is False
