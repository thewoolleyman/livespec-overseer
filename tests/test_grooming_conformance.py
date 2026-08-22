"""Conformance checks for the grooming operation's ledger invariants."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "grooming_conformance.py"

__all__: list[str] = []


class InvariantView(Protocol):
    key: str
    title: str
    status: str
    reason: str
    breaching_item_ids: tuple[str, ...]
    scanned_item_count: int


class ReportView(Protocol):
    invariants: tuple[InvariantView, ...]


class StageReportView(Protocol):
    measurement: object
    conformance: ReportView


class GroomingConformanceModule(Protocol):
    def evaluate_ledger_invariants(
        self,
        *,
        repo: Path,
        work_items: list[dict[str, object]],
        item_details_by_id: dict[str, list[str]] | None = None,
        sibling_item_ids_by_repo: dict[str, set[str]] | None = None,
        seat_anchor_epic_ids: set[str] | None = None,
    ) -> ReportView: ...

    def measure_grooming_inputs(
        self,
        *,
        repo: Path,
        work_items: list[dict[str, object]],
        proposed_changes_count: int,
    ) -> object: ...

    def merged_acceptance_criteria(self, *, item: dict[str, object]) -> str | None: ...

    def verify_grooming_stage(
        self,
        *,
        repo: Path,
        work_items: list[dict[str, object]],
        proposed_changes_count: int,
    ) -> StageReportView: ...


def grooming_conformance() -> GroomingConformanceModule:
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        _ = sys.path.insert(0, str(OVERSEER_DIR))
    module: ModuleType = importlib.import_module("grooming_conformance")
    return cast(GroomingConformanceModule, module)


def _repo(*, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "plan" / "existing").mkdir(parents=True)
    (repo / "SPECIFICATION" / "proposed_changes").mkdir(parents=True)
    _ = (repo / ".livespec.jsonc").write_text(
        '{"cross_repo_targets": {"sibling": {"github_url": "https://example.invalid/repo"}}}\n',
        encoding="utf-8",
    )
    return repo


def _item(
    *,
    item_id: str,
    status: str = "ready",
    parent: str | None = "plan-epic",
    acceptance_criteria: str | None = "Done is explicit.",
) -> dict[str, object]:
    row: dict[str, object] = {
        "id": item_id,
        "status": status,
        "issue_type": "feature",
        "metadata": {},
        "labels": [],
        "dependencies": [],
    }
    if parent is not None:
        row["parent"] = parent
    if acceptance_criteria is not None:
        row["acceptance_criteria"] = acceptance_criteria
    return row


def _with(
    *,
    row: dict[str, object],
    updates: dict[str, object],
) -> dict[str, object]:
    row.update(updates)
    return row


def _seat_anchor(*, item_id: str) -> dict[str, object]:
    return {
        "id": item_id,
        "status": "backlog",
        "issue_type": "epic",
        "title": "Foreman seat anchor",
        "description": "Ledger-held foreman handoff timeline.",
        "metadata": {},
        "labels": [],
        "dependencies": [],
    }


def _real_grooming_seat_anchor() -> dict[str, object]:
    return {
        "id": "overseer-qyli",
        "status": "backlog",
        "issue_type": "epic",
        "title": "livespec-overseer-grooming seat anchor rounds and handoffs",
        "description": (
            "Durable record for supervised grooming seat rounds; deliberately "
            "a seat anchor rather than a work epic."
        ),
        "metadata": {},
        "labels": ["intake:triaged"],
        "dependencies": [],
    }


def _by_key(*, report: ReportView, key: str) -> InvariantView:
    return {result.key: result for result in report.invariants}[key]


def test_reports_breaching_item_ids_and_unimplemented_invariants(*, tmp_path: Path) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _item(item_id="orphan", parent=None),
            _item(item_id="missing-acceptance", parent=None, acceptance_criteria=None),
            _with(
                row=_item(item_id="plan-epic", parent=None, acceptance_criteria=None),
                updates={"issue_type": "epic", "metadata": {"plan_slug": "existing"}},
            ),
            _seat_anchor(item_id="seat-anchor"),
            _item(item_id="native-open", status="open"),
            _item(item_id="native-deferred", status="deferred"),
        ],
        seat_anchor_epic_ids={"seat-anchor"},
    )

    assert _by_key(report=report, key="plan-rollup").breaching_item_ids == (
        "missing-acceptance",
        "orphan",
    )
    assert "non-seat-anchor" in _by_key(report=report, key="plan-rollup").scope
    assert _by_key(report=report, key="acceptance-present").breaching_item_ids == (
        "missing-acceptance",
    )
    assert _by_key(report=report, key="lifecycle-status").breaching_item_ids == (
        "native-deferred",
        "native-open",
    )
    assert _by_key(report=report, key="split-acceptance-label").status == (
        "unimplemented-pending-decision"
    )
    assert "no canonical expression" in _by_key(report=report, key="split-acceptance-label").reason
    assert _by_key(report=report, key="routing-field").status == ("unimplemented-pending-decision")
    assert "no backing field" in _by_key(report=report, key="routing-field").reason


def test_plan_rollup_exempts_registered_seat_anchor_from_real_record_shape(
    *,
    tmp_path: Path,
) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)

    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _real_grooming_seat_anchor(),
            _item(item_id="overseer-la2nfq", parent=None),
        ],
        seat_anchor_epic_ids={"overseer-qyli"},
    )

    plan_rollup = _by_key(report=report, key="plan-rollup")
    assert plan_rollup.breaching_item_ids == ("overseer-la2nfq",)
    assert "non-seat-anchor" in plan_rollup.scope


def test_plan_rollup_exempts_projection_spelled_anchor_but_reports_projection_spelled_bug(
    *,
    tmp_path: Path,
) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)

    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            {
                "id": "overseer-qyli",
                "status": "backlog",
                "type": "epic",
                "parent": None,
                "title": "livespec-overseer-grooming seat anchor rounds and handoffs",
                "notes": "Seat anchor record emitted by the merged work-item projection.",
                "labels": ["intake:triaged"],
                "dependencies": [],
            },
            {
                "id": "overseer-la2nfq",
                "status": "ready",
                "type": "bug",
                "parent": None,
                "title": "ordinary unparented bug",
                "notes": "Same projection spelling as the anchor control.",
                "labels": ["intake:triaged"],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
            },
        ],
        seat_anchor_epic_ids={"overseer-qyli"},
    )

    plan_rollup = _by_key(report=report, key="plan-rollup")
    assert plan_rollup.breaching_item_ids == ("overseer-la2nfq",)
    assert plan_rollup.scanned_item_count == 1


def test_plan_rollup_scope_says_when_seat_register_is_absent(*, tmp_path: Path) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)

    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[_real_grooming_seat_anchor()],
    )

    plan_rollup = _by_key(report=report, key="plan-rollup")
    assert plan_rollup.breaching_item_ids == ("overseer-qyli",)
    assert "seat-anchor register not supplied" in plan_rollup.scope


def test_acceptance_presence_uses_merged_projection_in_both_directions(
    *,
    tmp_path: Path,
) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _with(
                row=_item(item_id="metadata-only", acceptance_criteria=None),
                updates={"metadata": {"acceptance_criteria": "Creation-time acceptance."}},
            ),
            _with(
                row=_item(
                    item_id="native-wins-after-edit",
                    acceptance_criteria="Later native acceptance.",
                ),
                updates={"metadata": {"acceptance_criteria": ""}},
            ),
            _with(
                row=_item(item_id="missing", acceptance_criteria=None),
                updates={"metadata": {"acceptance_criteria": "   "}},
            ),
        ],
    )

    assert _by_key(report=report, key="acceptance-present").breaching_item_ids == ("missing",)
    assert (
        module.merged_acceptance_criteria(
            item={
                "acceptance_criteria": "Later native acceptance.",
                "metadata": {"acceptance_criteria": "Creation-time acceptance."},
            }
        )
        == "Later native acceptance."
    )


def test_delimiter_check_scans_details_only_for_dispatchable_items(*, tmp_path: Path) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    opening = chr(123) * 2
    closing = chr(125) * 2
    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _item(item_id="ready-clean"),
            _item(item_id="ready-comment"),
            _item(item_id="held-backlog", status="backlog"),
            _item(item_id="held-closed", status="closed"),
        ],
        item_details_by_id={
            "ready-comment": ["comment carries " + opening + " token " + closing],
            "held-backlog": ["held evidence " + opening],
            "held-closed": ["closed evidence " + closing],
        },
    )

    assert _by_key(report=report, key="dispatchable-delimiter").breaching_item_ids == (
        "ready-comment",
    )
    assert _by_key(report=report, key="dispatchable-delimiter").scanned_item_count == 2


def test_delimiter_check_flags_only_opening_template_forms(*, tmp_path: Path) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    opening = chr(123)
    closing = chr(125)
    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _item(item_id="closing-only"),
            _item(item_id="double-opening"),
            _item(item_id="percent-opening"),
        ],
        item_details_by_id={
            "closing-only": ["quoted payload ends " + closing + closing],
            "double-opening": ["template variable starts " + opening + opening],
            "percent-opening": ["template block starts " + opening + "%"],
        },
    )

    delimiter = _by_key(report=report, key="dispatchable-delimiter")
    assert delimiter.breaching_item_ids == ("double-opening", "percent-opening")
    assert "opening template delimiter" in delimiter.title


def test_cross_repo_edges_report_stringified_unlisted_and_unresolved_edges(
    *,
    tmp_path: Path,
) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _with(
                row=_item(item_id="stringified"),
                updates={"metadata": {"non_local_depends_on": "[not a parsed list]"}},
            ),
            _with(
                row=_item(item_id="invalid-entry"),
                updates={"metadata": {"non_local_depends_on": ["not a mapping"]}},
            ),
            _with(
                row=_item(item_id="unlisted"),
                updates={
                    "metadata": {
                        "non_local_depends_on": [{"repo": "missing-sibling", "work_item_id": "x-1"}]
                    }
                },
            ),
            _with(
                row=_item(item_id="unresolved"),
                updates={
                    "metadata": {
                        "non_local_depends_on": [
                            {"repo": "sibling", "work_item_id": "sibling-missing"}
                        ]
                    }
                },
            ),
            _with(
                row=_item(item_id="resolved"),
                updates={
                    "metadata": {
                        "non_local_depends_on": [
                            {"repo": "sibling", "work_item_id": "sibling-present"}
                        ]
                    }
                },
            ),
        ],
        sibling_item_ids_by_repo={"sibling": {"sibling-present"}},
    )

    assert _by_key(report=report, key="cross-repo-dependencies").breaching_item_ids == (
        "invalid-entry",
        "stringified",
        "unlisted",
        "unresolved",
    )


def test_projection_and_bd_shapes_converge_on_grooming_invariant_verdicts(
    *,
    tmp_path: Path,
) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    bd_report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            _with(
                row=_item(item_id="plan-anchor", parent=None, acceptance_criteria=None),
                updates={"issue_type": "epic", "metadata": {"plan_slug": "existing"}},
            ),
            _with(
                row=_item(item_id="unslugged-epic", parent=None),
                updates={"issue_type": "epic"},
            ),
            _item(item_id="missing-acceptance", acceptance_criteria=None),
            _item(item_id="terminal", status="closed"),
            _item(item_id="bad-status", status="open"),
            _with(
                row=_item(item_id="resolved-dependency"),
                updates={
                    "depends_on": [{"kind": "local", "work_item_id": "plan-anchor"}],
                    "metadata": {
                        "non_local_depends_on": [
                            {"repo": "sibling", "work_item_id": "sibling-present"}
                        ]
                    },
                },
            ),
            _with(
                row=_item(item_id="unresolved-dependency"),
                updates={
                    "metadata": {
                        "non_local_depends_on": [
                            {"repo": "sibling", "work_item_id": "sibling-missing"}
                        ]
                    }
                },
            ),
            _with(
                row=_item(item_id="local-only-dependency"),
                updates={"depends_on": [{"kind": "local", "work_item_id": "plan-anchor"}]},
            ),
        ],
        sibling_item_ids_by_repo={"sibling": {"sibling-present"}},
    )
    projection_report = module.evaluate_ledger_invariants(
        repo=repo,
        work_items=[
            {
                "id": "plan-anchor",
                "status": "backlog",
                "type": "epic",
                "parent": None,
                "notes": "plan_slug=existing",
                "spec_commitment_hint": "plan:existing",
                "labels": [],
                "dependencies": [],
            },
            {
                "id": "unslugged-epic",
                "status": "ready",
                "type": "epic",
                "parent": None,
                "labels": [],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
            },
            {
                "id": "missing-acceptance",
                "status": "ready",
                "type": "bug",
                "parent": "plan-anchor",
                "labels": [],
                "dependencies": [],
            },
            {
                "id": "terminal",
                "status": "done",
                "type": "bug",
                "parent": "plan-anchor",
                "labels": [],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
            },
            {
                "id": "bad-status",
                "status": "open",
                "type": "bug",
                "parent": "plan-anchor",
                "labels": [],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
            },
            {
                "id": "resolved-dependency",
                "status": "ready",
                "type": "bug",
                "parent": "plan-anchor",
                "labels": [],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
                "depends_on": [
                    {"kind": "local", "work_item_id": "plan-anchor"},
                    {"repo": "sibling", "work_item_id": "sibling-present"},
                ],
            },
            {
                "id": "unresolved-dependency",
                "status": "ready",
                "type": "bug",
                "parent": "plan-anchor",
                "labels": [],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
                "depends_on": [{"repo": "sibling", "work_item_id": "sibling-missing"}],
            },
            {
                "id": "local-only-dependency",
                "status": "ready",
                "type": "bug",
                "parent": "plan-anchor",
                "labels": [],
                "dependencies": [],
                "acceptance_criteria": "Done is explicit.",
                "depends_on": [{"kind": "local", "work_item_id": "plan-anchor"}],
            },
        ],
        sibling_item_ids_by_repo={"sibling": {"sibling-present"}},
    )

    expected_breaches = {
        "plan-rollup": ("unslugged-epic",),
        "acceptance-present": ("missing-acceptance",),
        "lifecycle-status": ("bad-status",),
        "cross-repo-dependencies": ("unresolved-dependency",),
    }
    for key, breaching_ids in expected_breaches.items():
        bd_check = _by_key(report=bd_report, key=key)
        projection_check = _by_key(report=projection_report, key=key)
        assert bd_check.breaching_item_ids == breaching_ids
        assert projection_check.breaching_item_ids == breaching_ids
        assert bd_check.scanned_item_count > 0
        assert projection_check.scanned_item_count > 0

    projection_cross_repo = _by_key(report=projection_report, key="cross-repo-dependencies")
    assert projection_cross_repo.scanned_item_count == 3
    assert "local-only-dependency" not in projection_cross_repo.breaching_item_ids


def test_measure_stage_is_reentrant_and_later_stage_derives_inputs(*, tmp_path: Path) -> None:
    module = grooming_conformance()
    repo = _repo(tmp_path=tmp_path)
    items = [
        _with(
            row=_item(item_id="ready-a"),
            updates={"labels": ["intake:triaged"]},
        ),
        _with(
            row=_item(item_id="label-field-string"),
            updates={"labels": "intake:triaged"},
        ),
        _with(
            row=_item(item_id="mixed-labels"),
            updates={"labels": ["intake:triaged", 7]},
        ),
        _item(item_id="backlog-b", status="backlog", parent=None),
        _with(
            row=_item(item_id="plan-epic", parent=None, acceptance_criteria=None),
            updates={"issue_type": "epic", "metadata": {"plan_slug": "existing"}},
        ),
    ]

    first = module.measure_grooming_inputs(
        repo=repo,
        work_items=items,
        proposed_changes_count=0,
    )
    second = module.measure_grooming_inputs(
        repo=repo,
        work_items=items,
        proposed_changes_count=0,
    )
    report = module.verify_grooming_stage(
        repo=repo,
        work_items=items,
        proposed_changes_count=0,
    )

    assert first == second
    assert first == second
    assert report.measurement == first
    assert _by_key(report=report.conformance, key="plan-rollup").breaching_item_ids == (
        "backlog-b",
    )
