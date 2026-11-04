"""Styled Codex-composer evidence for safe busy-pane delivery."""

from __future__ import annotations

import re

__all__: list[str] = ["codex_composer_empty"]

_SGR = r"\x1b\[[0-9;]*m"
_COLOUR_SGR = r"\x1b\[(?:(?:3|4)[0-7]|(?:38|48);(?:5;\d+|2;\d+;\d+;\d+))m"
_DIM_COMPOSER_RE = re.compile(
    rf"^(?:{_SGR})*›(?:{_SGR}|\s)*\x1b\[2m(?:{_COLOUR_SGR})*"
    rf"(?=[^\x1b\r\n]*\S)(?:[^\x1b\r\n]|{_COLOUR_SGR})*\x1b\[0m(?:{_SGR}|\s)*$"
)


def codex_composer_empty(*, capture_text: str) -> bool:
    """Whether a visible Codex composer has only its dim-generated placeholder.

    Placeholder wording rotates, so only its styling is evidence. A malformed capture,
    an unstyled glyph, or a glyph after the dim span is not evidence of an empty input.
    """
    return any(_DIM_COMPOSER_RE.fullmatch(raw) is not None for raw in capture_text.splitlines())
