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
    "composer_empty",
    "delivered",
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
# Codex 0.163.0 collapses a multi-line bracketed paste to this prompt-row
# placeholder. As with Claude's placeholder, it proves a payload landed only
# for a multi-line payload; a one-line paste must still expose its first line.
_CODEX_PASTE_PLACEHOLDER = re.compile(r"› \[Pasted Content \d+ chars\]")


def prompt_visible(*, capture: str, text: str) -> bool:
    first_line = text.partition("\n")[0].strip()
    box = signals.input_box_text(capture_text=capture)
    collapsed = ("\n" in text.strip()) & (
        _CLAUDE_PASTE_PLACEHOLDER.fullmatch(box or "") is not None
    )
    claude_visible = (box == first_line) | collapsed
    codex_capture = signals.strip_ansi(text=capture)
    codex_collapsed = ("\n" in text.strip()) & (
        _CODEX_PASTE_PLACEHOLDER.search(codex_capture) is not None
    )
    codex_visible = bool(first_line) & ((f"› {first_line}" in codex_capture) | codex_collapsed)
    return bool(claude_visible | codex_visible)


def submitted(*, capture: str) -> bool:
    """Return true only when runtime activity proves the submitted turn began."""
    return signals.is_busy(capture_text=capture)


def composer_empty(*, capture: str) -> bool:
    """A Claude composer that is present and holds nothing.

    Codex cannot tell its placeholder from typed text in a capture, so a Codex pane is
    never positively empty here and its delivery is still confirmed only by activity.
    """
    return signals.input_box_ready(capture_text=capture) and (
        signals.input_box_text(capture_text=capture) is None
    )


def delivered(*, capture: str) -> bool:
    """Delivery is proven by the turn starting OR by the payload having left the input.

    Callers ask this only AFTER the payload was observed in the composer and Enter was
    sent, so an empty composer means the payload went somewhere: submitted, or queued
    behind a running turn. Measured 2026-10-15 (SPECIFICATION v059): reading only a
    busy frame inside a one-second window reported delivered wrap-ups as failed
    (petri-factory-on-gmktec 08:09Z, gitops-fleet-capacity-monitoring 2026-10-14).
    """
    return submitted(capture=capture) or composer_empty(capture=capture)


def resolved(
    *,
    capture: str,
    prompt_visible: CapturePredicate,
    submitted: CapturePredicate,
) -> bool:
    return bool(submitted(capture=capture) | prompt_visible(capture=capture))
