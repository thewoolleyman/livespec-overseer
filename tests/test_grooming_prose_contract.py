"""Contract guard for the shared grooming prose."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

__all__: list[str] = []

ROOT = Path(__file__).resolve().parent.parent
PROSE = ROOT / ".claude-plugin" / "prose" / "grooming.md"
OVERSEER_DIR = ROOT / "overseer"
MODULE_PATH = OVERSEER_DIR / "grooming_conformance.py"
BINDINGS = (
    ROOT / ".claude-plugin" / "skills" / "grooming" / "SKILL.md",
    ROOT / ".claude-plugin" / ".codex-plugin" / "skills" / "grooming" / "SKILL.md",
    ROOT / ".claude-plugin" / ".pi-plugin" / "skills" / "livespec-overseer-grooming" / "SKILL.md",
)


class MeasurementView(Protocol):
    untriaged_item_ids: tuple[str, ...]


class GroomingConformanceModule(Protocol):
    def measure_grooming_inputs(
        self,
        *,
        repo: Path,
        work_items: list[dict[str, object]],
        proposed_changes_count: int,
    ) -> MeasurementView: ...


def grooming_conformance() -> GroomingConformanceModule:
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        _ = sys.path.insert(0, str(OVERSEER_DIR))
    module: ModuleType = importlib.import_module("grooming_conformance")
    return cast(GroomingConformanceModule, module)


def _repo(*, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "plan").mkdir(parents=True)
    (repo / "SPECIFICATION" / "proposed_changes").mkdir(parents=True)
    return repo


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


def test_grooming_prose_reconciles_bucketing_blocked_unparented_rows() -> None:
    text = PROSE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "BUCKETING-BLOCKED provenance for the pass report" in normalized
    assert "not a ledger marker and not an invariant-1 exemption" in normalized
    assert "Ledger Invariants section still requires the row to be reported" in normalized
    assert "Bucketing-blocked rows are the other recognized unparented provenance" in normalized
    assert "zero new-thread allowance and no existing thread is a truthful home" in normalized
    assert "leave the row unparented and report the blocked bucketing decision" in normalized
    assert "rather than manufacture untruthful membership" in normalized
    assert "Nothing in the ledger substrate distinguishes that row" in normalized
    assert "distinguishable only by the pass's own report" in normalized
    assert "budget, live-thread count, overflow, and reclaimable thread list" in normalized
    assert "reported rather than silently tolerated" in normalized
    assert "not a license to stop reporting the row" in normalized
    assert (
        "no recognized provenance--neither deferral-successor nor bucketing-blocked" in normalized
    )


def test_grooming_stage_three_freshness_guard_rechecks_preexisting_rows(
    *,
    tmp_path: Path,
) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    stale_snapshot = [
        {
            "id": "left-scope",
            "status": "backlog",
            "labels": [],
            "metadata": {},
            "dependencies": [],
        },
        {
            "id": "still-scoped",
            "status": "backlog",
            "labels": [],
            "metadata": {},
            "dependencies": [],
        },
    ]
    fresh_snapshot = [
        {
            "id": "left-scope",
            "status": "closed",
            "labels": [],
            "metadata": {},
            "dependencies": [],
        },
        {
            "id": "still-scoped",
            "status": "backlog",
            "labels": [],
            "metadata": {},
            "dependencies": [],
        },
    ]

    measured = module.measure_grooming_inputs(
        repo=repo,
        work_items=stale_snapshot,
        proposed_changes_count=0,
    )
    refreshed = module.measure_grooming_inputs(
        repo=repo,
        work_items=fresh_snapshot,
        proposed_changes_count=0,
    )

    assert measured.untriaged_item_ids == ("left-scope", "still-scoped")
    assert refreshed.untriaged_item_ids == ("still-scoped",)

    text = PROSE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "Before writing any status to a pre-existing row" in normalized
    assert "re-read that row's current status" in normalized
    assert "If the row has left the stage's declared scope" in normalized
    assert "skip the write" in normalized
    assert "report the skipped row explicitly in the round record" in normalized
    assert "The round record must name skipped rows as well as written rows" in normalized
    assert "a skip is otherwise unrecoverable" in normalized
    assert "This narrows the stale-snapshot window; it does not make stage 3 atomic" in normalized
    assert "between the freshness read and the status write" in normalized
