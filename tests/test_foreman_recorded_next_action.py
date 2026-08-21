"""Tests for the recorded-next-action handoff parser."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GROOMING_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "grooming.md"


def recorded_next_action_module() -> ModuleType:
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_recorded_next_action")


def emitted_plan_handoff(*, parser: ModuleType) -> str:
    """Return the heading/body form the plan primitive contract emits."""
    primitive = _GROOMING_PROSE.read_text(encoding="utf-8")
    phrase = "opening handoff with exactly one next action"
    assert phrase in primitive
    assert getattr(parser, "EMITTING_PLAN_PRIMITIVE_NEXT_ACTION_PHRASE", None) == phrase
    return """
# Handoff

The current scope event remains in force.

## NEXT ACTION (exactly one)

Implement overseer-swzvdg through the factory path.
""".strip()


def test_next_actions_reads_the_plan_primitive_heading_form():
    parser = recorded_next_action_module()
    assert parser.next_actions(handoff_text=emitted_plan_handoff(parser=parser)) == [
        "Implement overseer-swzvdg through the factory path."
    ]


def test_next_actions_keeps_zero_and_multiple_handoffs_discriminating():
    parser = recorded_next_action_module()
    assert parser.next_actions(handoff_text="# Handoff\n\nNo queued action is recorded.") == []
    assert parser.next_actions(
        handoff_text="""
# Handoff

## NEXT ACTION (exactly one)

Implement overseer-swzvdg.1.

## NEXT ACTION

Implement overseer-swzvdg.2.
""".strip()
    ) == [
        "Implement overseer-swzvdg.1.",
        "Implement overseer-swzvdg.2.",
    ]
