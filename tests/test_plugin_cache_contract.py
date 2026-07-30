"""Regression tests for paths that must survive plugin-cache materialization."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
OVERSEER_PROSE = ROOT / ".claude-plugin" / "prose" / "overseer.md"


def test_overseer_prose_does_not_require_unshipped_agent_disciplines():
    prose = OVERSEER_PROSE.read_text(encoding="utf-8")

    assert ".ai/agent-disciplines.md" in prose
    assert "optional external cross-reference" in prose
    assert "Do not search another host checkout for that file" in prose
    assert "read those alongside this skill" not in prose
