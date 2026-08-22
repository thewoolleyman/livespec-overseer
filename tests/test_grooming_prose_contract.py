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
    assert "three implemented invariants that need no optional evidence" in normalized
    assert "only with item detail text supplied for comments and notes" in normalized
    assert "only with sibling id sets supplied for every referenced sibling repo" in normalized
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


def test_grooming_prose_deferral_successors_do_not_weaken_invariant_one() -> None:
    text = PROSE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "Every non-done item rolls up to a plan epic" in normalized
    assert "A deferral successor is still parented to the epic it defers from" in normalized
    assert "disposed for archive purposes by a paired carry-forward marker" in normalized
    assert "not by being left unparented" in normalized
    assert "successor must carry the reference to the deferring epic" in normalized
    assert "deferring epic's own record must name that successor id" in normalized
    assert "That archive gate behavior is not implemented here yet" in normalized
    assert "bd-ib-tl5u" in text

    for measured_id in (
        "overseer-n1ai",
        "overseer-5416",
        "overseer-6bx5",
        "overseer-cv06",
        "overseer-157q",
    ):
        assert measured_id in text

    assert "do not normalize the workaround into a new invariant exemption" in normalized
    assert "An ordinary unparented non-done item" in normalized
    assert "remains a genuine invariant-1 breach" in normalized
