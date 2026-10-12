"""Runtime-neutral pane signals for verified native prompt submission."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import herdr_identity
import herdr_write
import signals

__all__: list[str] = [
    "CapturePredicate",
    "HerdrInput",
    "PromptState",
    "prompt_visible",
    "resolved",
    "submitted",
]


class HerdrInput(Protocol):
    def bracketed_paste(
        self, *, target: herdr_identity.HerdrPaneTarget, text: str
    ) -> herdr_write.WriteOutcome: ...

    def send_enter(self, *, target: herdr_identity.HerdrPaneTarget) -> herdr_write.WriteOutcome: ...


class CapturePredicate(Protocol):
    def __call__(self, *, capture: str) -> bool: ...


@dataclass(frozen=True, kw_only=True)
class PromptState:
    text: str
    phase: str
    effect_unknown: bool


# Claude collapses a multi-line bracketed paste in its composer to this placeholder
# rather than rendering the payload's first line (measured live 2026-10-12: a wrap-up
# paste showed as `[Pasted text #1 +41 lines]`, was judged not to have landed, and its
# Enter was never sent). A single-line payload is never collapsed, so the placeholder
# only stands in for a multi-line one.
_CLAUDE_PASTE_PLACEHOLDER = re.compile(r"\[Pasted text #\d+(?: \+\d+ lines)?\]")


def prompt_visible(*, capture: str, text: str) -> bool:
    first_line = text.partition("\n")[0].strip()
    box = signals.input_box_text(capture_text=capture)
    collapsed = ("\n" in text.strip()) & (
        _CLAUDE_PASTE_PLACEHOLDER.fullmatch(box or "") is not None
    )
    claude_visible = (box == first_line) | collapsed
    codex_visible = bool(first_line) & (f"› {first_line}" in signals.strip_ansi(text=capture))
    return bool(claude_visible | codex_visible)


def submitted(*, capture: str) -> bool:
    """Return true only when runtime activity proves the submitted turn began."""
    return signals.is_busy(capture_text=capture)


def resolved(
    *,
    capture: str,
    prompt_visible: CapturePredicate,
    submitted: CapturePredicate,
) -> bool:
    return bool(submitted(capture=capture) | prompt_visible(capture=capture))
