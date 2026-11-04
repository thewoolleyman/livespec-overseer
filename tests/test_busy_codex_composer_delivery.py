"""Regression tests for the busy-pane composer evidence before wrap-up delivery."""

import _supervisor_busy_delivery

__all__: list[str] = []


_CODEX_BUSY_PREFIX = (
    "\u001b[0m\u001b[1m\u001b[48;2;49;52;57m›\u001b[0m" "\u001b[48;2;49;52;57m \u001b[0m"
)
_CODEX_STATUSLINE = "  gpt-5.5 high · /x/repo · Context 35% left · some-topic\n"
_CODEX_BUSY_MARKER = "◦ Working (1s • esc to interrupt)\n"


def test_busy_codex_composer_requires_a_dim_placeholder():
    """Only the measured dim placeholder proves a busy Codex composer is empty."""
    dim_placeholder = (
        _CODEX_BUSY_MARKER
        + _CODEX_BUSY_PREFIX
        + "\u001b[2m\u001b[48;2;49;52;57mAsk Codex to do anything\u001b[0m"
        + "\u001b[48;2;49;52;57m   \u001b[0m\n"
        + _CODEX_STATUSLINE
    )
    typed_text = (
        _CODEX_BUSY_MARKER
        + _CODEX_BUSY_PREFIX
        + "\u001b[48;2;49;52;57mwrite the release note\u001b[0m\n"
        + _CODEX_STATUSLINE
    )

    assert _supervisor_busy_delivery.input_empty(capture=dim_placeholder, is_codex=True) is True
    assert _supervisor_busy_delivery.input_empty(capture=typed_text, is_codex=True) is False
    assert _supervisor_busy_delivery.input_empty(capture="", is_codex=True) is False
