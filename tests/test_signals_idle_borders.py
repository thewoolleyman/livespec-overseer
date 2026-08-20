"""Regression coverage for Claude titled input-box border shapes."""

import pytest
import signals

__all__: list[str] = []

_PURE_RULE = "─" * 40


def _box_capture(*, top_border: str, prompt: str = "❯ ") -> str:
    return "\n".join(
        [
            "● prior response",
            top_border,
            prompt,
            _PURE_RULE,
            "  Opus 4.8 (1M context) | /x/repo | Ctx: 14% left",
            "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
            "",
        ]
    )


_CLAUDE_2_1_237_TITLED_IDLE_CAPTURE = _box_capture(top_border="──── livespec-overseer-foreman ─")

_CLAUDE_2_1_235_TITLED_IDLE_CAPTURE = _box_capture(top_border="──── livespec-overseer-foreman ──")

_TITLELESS_IDLE_CAPTURE = _box_capture(top_border=_PURE_RULE)


def _assert_empty_claude_prompt(*, capture_text: str) -> None:
    assert signals.is_idle_input(capture_text=capture_text) is True
    assert signals.input_box_ready(capture_text=capture_text) is True
    assert signals.input_box_text(capture_text=capture_text) is None


@pytest.mark.parametrize(
    "capture",
    [
        _CLAUDE_2_1_237_TITLED_IDLE_CAPTURE,
        _CLAUDE_2_1_235_TITLED_IDLE_CAPTURE,
        _TITLELESS_IDLE_CAPTURE,
    ],
)
def test_empty_claude_prompt_accepts_measured_titled_borders_and_titleless_rule(
    *,
    capture: str,
) -> None:
    _assert_empty_claude_prompt(capture_text=capture)


def test_input_box_text_returns_typed_text_and_is_not_idle() -> None:
    capture = _box_capture(top_border=_PURE_RULE, prompt="❯ overseer-declare ready")
    assert signals.input_box_text(capture_text=capture) == "overseer-declare ready"
    assert signals.is_idle_input(capture_text=capture) is False
    assert signals.input_box_ready(capture_text=capture) is False


def test_plain_line_ending_in_one_rule_character_is_not_a_border() -> None:
    capture = _box_capture(top_border="plain prose that happens to end in a rule ─")
    assert signals.is_idle_input(capture_text=capture) is False
    assert signals.input_box_ready(capture_text=capture) is False
    assert signals.input_box_text(capture_text=capture) is None
