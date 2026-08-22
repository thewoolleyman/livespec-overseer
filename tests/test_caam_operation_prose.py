"""The caam operation prose must expose every operator-visible flag."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PROSE = ROOT / ".claude-plugin" / "prose" / "caam-anthropic-loop.md"
ENFORCEMENT_SOURCE = ROOT / "overseer" / "caam_enforcement.py"
WARM_SOURCE = ROOT / "overseer" / "caam_warm.py"

EXPECTED_FORWARDABLE_FLAGS = (
    "--force",
    "--dry-run",
    "--no-models",
    "--foreman-model=<fable|opus|auto>",
    "--no-warm",
)


def test_caam_prose_lists_every_source_backed_operator_flag() -> None:
    """Source-backed operator flags must not land after prose and stay hidden."""
    prose = PROSE.read_text(encoding="utf-8")
    enforcement_source = ENFORCEMENT_SOURCE.read_text(encoding="utf-8")
    warm_source = WARM_SOURCE.read_text(encoding="utf-8")

    assert "foreman_model" in enforcement_source
    assert "no_warm" in warm_source
    for flag in EXPECTED_FORWARDABLE_FLAGS:
        assert flag in prose


def test_caam_prose_explains_foreman_pin_persistence_and_clear() -> None:
    prose = PROSE.read_text(encoding="utf-8")

    assert "pin persists" in prose
    assert "later scheduled ticks" in prose
    assert "`--foreman-model=auto` clears the pin" in prose
