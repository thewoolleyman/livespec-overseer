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


def test_grooming_prose_names_ledger_projection_and_record_shape_traps() -> None:
    text = PROSE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "implementation.plugin" in text
    assert "list-work-items --json" in text
    assert "Runtime neutrality comes from resolving" in normalized
    assert "not from hard-coding a substrate command" in normalized
    assert "five implemented invariants" in normalized
    assert "split-acceptance-label" in text
    assert "routing-field" in text

    for trap_text in (
        "Comments are not in the record",
        "Records are omitempty-sparse",
        "`dependencies` is one heterogeneous array",
        "A bounded query's negative result is a statement about the bound",
    ):
        assert trap_text in normalized

    for tell_text in (
        "Tell: a read-back after a successful comment write reports zero comments",
        "Tell: a field is absent on a large minority of records",
        "Tell: every target reads as `None`",
        "Tell: a surprising absence",
    ):
        assert tell_text in normalized
