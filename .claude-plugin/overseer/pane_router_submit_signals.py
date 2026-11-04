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
    "codex_composer_empty",
    "codex_composer_text",
    "composer_empty",
    "delivered",
    "prompt_pending",
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
_CODEX_CONTEXT_STATUSLINE = re.compile(r"\bContext \d+% left\b")
_CODEX_CWD_STATUSLINE = re.compile(r" · (?:~|/[^ ·]+)(?: · |$)")


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


def prompt_pending(*, capture: str, text: str) -> bool:
    """Whether the exact payload sits in an input row, never in transcript scrollback.

    A Codex pane is judged only by its composer row (the row above the statusline), so
    the payload echoed in the transcript above an empty composer is not pending input.
    """
    composer = codex_composer_text(capture=capture)
    if composer is None:
        return prompt_visible(capture=capture, text=text)
    first_line = text.partition("\n")[0].strip()
    collapsed = ("\n" in text.strip()) & (
        _CODEX_PASTE_PLACEHOLDER.fullmatch(f"› {composer}") is not None
    )
    return bool(first_line) & ((composer == first_line) | collapsed)


def codex_composer_text(*, capture: str) -> str | None:
    """Return the current Codex composer payload, normalized across wrapped rows.

    A pane capture contains transcript and composer text in one stream.  The only
    input that can authorize an Enter retry is the composer block immediately before
    Codex's statusline: its ``›`` row and any contiguous indented continuation rows.
    A warnings footer may appear below that line, so the statusline is identified by
    its context indicator or cwd-bearing status shape rather than every row with a
    separator. Blank spacer rows above it are layout, not input. Anchoring the block at
    the statusline prevents an identical transcript line from being treated as pending
    composer text.
    """
    lines = signals.strip_ansi(text=capture).splitlines()
    statusline = next(
        (
            index
            for index in range(len(lines) - 1, -1, -1)
            if _CODEX_CONTEXT_STATUSLINE.search(lines[index]) is not None
            or _CODEX_CWD_STATUSLINE.search(lines[index]) is not None
        ),
        None,
    )
    if statusline is None:
        return None
    last_content = statusline - 1
    while last_content >= 0 and not lines[last_content].strip():
        last_content -= 1
    first_content = last_content
    while first_content > 0 and lines[first_content].startswith((" ", "\t")):
        first_content -= 1
    composer = lines[first_content].lstrip()
    if not composer.startswith("›"):
        return None
    return " ".join(
        part.strip() for part in (composer[1:], *lines[first_content + 1 : last_content + 1])
    ).strip()


def codex_composer_empty(*, capture: str) -> bool:
    """Whether a positively idle Codex composer has no visible input text."""
    return signals.is_codex_idle_input(capture_text=capture) and (
        codex_composer_text(capture=capture) == ""
    )


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
