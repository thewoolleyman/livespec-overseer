"""Runtime-neutral pane signals for verified native prompt submission."""

from __future__ import annotations

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


def prompt_visible(*, capture: str, text: str) -> bool:
    first_line = text.partition("\n")[0].strip()
    claude_visible = signals.input_box_text(capture_text=capture) == first_line
    codex_visible = bool(first_line) & (f"› {first_line}" in signals.strip_ansi(text=capture))
    return bool(claude_visible | codex_visible)


def submitted(*, capture: str) -> bool:
    return bool(
        signals.is_busy(capture_text=capture) | signals.input_box_ready(capture_text=capture)
    )


def resolved(
    *,
    capture: str,
    prompt_visible: CapturePredicate,
    submitted: CapturePredicate,
) -> bool:
    return bool(submitted(capture=capture) | prompt_visible(capture=capture))
