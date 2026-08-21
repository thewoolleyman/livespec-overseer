"""The foreman prose must own its self-initiated wind-down floor.

The foreman is an LLM-operated surface: the prose is executable control flow,
not explanatory documentation. This gate pins the floor-triggered behavior that
prevents a foreman from waiting indefinitely for a daemon wrap-up that may never
arrive.
"""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PROSE = ROOT / ".claude-plugin" / "prose" / "foreman.md"


def _prose() -> str:
    return PROSE.read_text(encoding="utf-8")


def test_self_winddown_floor_and_sequence_are_declared() -> None:
    text = _prose()
    normalized = " ".join(text.split())

    assert "### Self-initiated wind-down floor" in text
    assert "At or below 25% remaining context" in normalized
    assert "in the same tick" in normalized
    assert "Append the handoff entry" in text
    assert "Read the updated record back" in text
    assert "overseer-declare ready" in text
    assert "without raising a picker" in normalized
    assert "without waiting for the daemon's wrap-up" in normalized


def test_wrapup_above_floor_and_ready_finality_are_declared() -> None:
    text = _prose()
    normalized = " ".join(text.split())

    assert "arrives while you are still above 25%" in normalized
    assert "acknowledge that you are winding down" in normalized
    assert "follow the wrap-up" in text
    assert "A `ready` declaration is final for that session" in text
    assert "No further ticks" in text


def test_self_restart_wording_does_not_land_in_this_contract() -> None:
    text = _prose().lower()

    assert "self-restart" not in text
    assert "restart itself" not in text
