"""Delivery contract for the dual-backend overseer operator surface."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
OPERATOR_CONTRACT = ROOT / ".claude-plugin" / "prose" / "overseer.md"


def test_the_shipped_contract_bootstraps_the_nearest_verified_backend_without_an_override() -> None:
    prose = OPERATOR_CONTRACT.read_text(encoding="utf-8")

    assert "Linux with either tmux or Herdr" in prose
    assert "nearest positively verified terminal owner" in prose
    assert '"$OVERSEER_START"' in prose
    assert '"$OVERSEER_START" --backend' not in prose
    assert "same original LLM pane" in prose
    assert "running bootstrap again" in prose
