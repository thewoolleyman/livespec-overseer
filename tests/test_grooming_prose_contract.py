"""Contract guard for the shared grooming prose."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PROSE = ROOT / ".claude-plugin" / "prose" / "grooming.md"
BINDINGS = (
    ROOT / ".claude-plugin" / "skills" / "grooming" / "SKILL.md",
    ROOT / ".claude-plugin" / ".codex-plugin" / "skills" / "grooming" / "SKILL.md",
    ROOT / ".claude-plugin" / ".pi-plugin" / "skills" / "livespec-overseer-grooming" / "SKILL.md",
)


def test_grooming_prose_exists_and_carries_no_template_delimiters() -> None:
    assert PROSE.is_file()
    text = PROSE.read_text(encoding="utf-8")
    opening = chr(123) * 2
    closing = chr(125) * 2
    assert opening not in text
    assert closing not in text


def test_grooming_bindings_reference_shared_prose_when_present() -> None:
    existing = [path for path in BINDINGS if path.exists()]
    if not existing:
        return

    assert existing == list(
        BINDINGS
    ), "once any grooming binding lands, all three thin bindings must land together"

    for binding in existing:
        assert "prose/grooming.md" in binding.read_text(encoding="utf-8")
