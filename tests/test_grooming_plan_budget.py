"""Regression coverage for the grooming plan-budget resolver."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "grooming_plan_budget.py"

__all__: list[str] = []


def grooming_plan_budget():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("grooming_plan_budget")


def _repo(*, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "SPECIFICATION" / "proposed_changes").mkdir(parents=True)
    (repo / "plan").mkdir()
    (repo / ".livespec.jsonc").write_text(
        '{"spec_root": "SPECIFICATION"}\n',
        encoding="utf-8",
    )
    return repo


def _item(*, item_id: str, status: str = "ready") -> dict[str, object]:
    return {"id": item_id, "issue_type": "feature", "status": status}


def _anchor(*, item_id: str, slug: str, status: str = "open") -> dict[str, object]:
    return {
        "id": item_id,
        "issue_type": "epic",
        "status": status,
        "metadata": {"plan_slug": slug},
    }


def test_worked_example_auto_budget_and_allowance(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)

    result = module.resolve_plan_budget(
        repo=repo,
        proposed_changes_count=2,
        work_items=[_item(item_id=str(index)) for index in range(55)],
        live_plan_slugs=["alpha", "beta"],
    )

    assert result.path == "auto"
    assert result.governing_path == "population-derived"
    assert result.drainable_population == 57
    assert result.raw_auto_budget == 5
    assert result.budget == 5
    assert result.live_thread_count == 2
    assert result.new_thread_allowance == 3


def test_auto_budget_clamps_at_both_ends_and_reports_path(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)

    low = module.resolve_plan_budget(repo=repo, proposed_changes_count=1, work_items=[])
    high = module.resolve_plan_budget(
        repo=repo,
        proposed_changes_count=0,
        work_items=[_item(item_id=str(index)) for index in range(241)],
    )

    assert low.raw_auto_budget == 1
    assert low.budget == 2
    assert low.governing_path == "min-clamped"
    assert high.raw_auto_budget == 21
    assert high.budget == 20
    assert high.governing_path == "max-clamped"


def test_default_max_leaves_recorded_fleet_populations_population_derived(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)

    examples = {
        "livespec": 144,
        "livespec-dev-tooling": 231,
        "livespec-orchestrator-beads-fabro": 206,
        "livespec-runtime": 16,
        "livespec-console-beads-fabro": 38,
        "livespec-overseer": 133,
    }

    results = {
        name: module.resolve_plan_budget(
            repo=repo,
            proposed_changes_count=population,
            work_items=[],
        )
        for name, population in examples.items()
    }

    assert [(name, result.raw_auto_budget) for name, result in results.items()] == [
        ("livespec", 12),
        ("livespec-dev-tooling", 20),
        ("livespec-orchestrator-beads-fabro", 18),
        ("livespec-runtime", 2),
        ("livespec-console-beads-fabro", 4),
        ("livespec-overseer", 12),
    ]
    assert all(result.governing_path == "population-derived" for result in results.values())


def test_config_pinned_budget_overrides_different_auto_value(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)
    (repo / ".livespec.jsonc").write_text(
        '{"spec_root": "SPECIFICATION", "grooming": {"plan_budget": 4}}\n',
        encoding="utf-8",
    )

    result = module.resolve_plan_budget(
        repo=repo,
        proposed_changes_count=0,
        work_items=[_item(item_id=str(index)) for index in range(241)],
    )

    assert result.path == "explicit"
    assert result.governing_path == "explicit"
    assert result.raw_auto_budget == 21
    assert result.budget == 4


def test_malformed_config_falls_back_to_auto(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)
    (repo / ".livespec.jsonc").write_text(
        '{"grooming": {"plan_budget": "four", "items_per_plan": "six"}}\n',
        encoding="utf-8",
    )

    result = module.resolve_plan_budget(
        repo=repo,
        proposed_changes_count=0,
        work_items=[_item(item_id=str(index)) for index in range(25)],
    )

    assert result.path == "auto"
    assert result.items_per_plan == 12
    assert result.budget == 3


def test_live_thread_count_uses_distinct_union_from_dirs_and_anchor_epics(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)
    (repo / "plan" / "directory-only").mkdir()
    (repo / "plan" / "shared").mkdir()
    (repo / "plan" / "archive").mkdir()
    (repo / "plan" / "archive" / "old").mkdir()

    result = module.resolve_plan_budget(
        repo=repo,
        proposed_changes_count=57,
        work_items=[
            _anchor(item_id="anchor-1", slug="anchor-only"),
            _anchor(item_id="anchor-2", slug="shared"),
            _anchor(item_id="anchor-3", slug="anchor-only"),
            _anchor(item_id="anchor-4", slug="old", status="closed"),
        ],
    )

    assert result.live_thread_slugs == ("anchor-only", "directory-only", "shared")
    assert result.live_thread_count == 3
    assert result.budget == 5
    assert result.new_thread_allowance == 2


def test_allowance_floors_at_zero_when_live_threads_exceed_budget(*, tmp_path):
    module = grooming_plan_budget()
    repo = _repo(tmp_path=tmp_path)

    result = module.resolve_plan_budget(
        repo=repo,
        proposed_changes_count=57,
        work_items=[_item(item_id="one")],
        live_plan_slugs=["one", "two", "three", "four", "five", "six"],
    )

    assert result.budget == 5
    assert result.live_thread_count == 6
    assert result.new_thread_allowance == 0


def test_counts_pending_proposed_changes_under_configured_spec_root(*, tmp_path):
    module = grooming_plan_budget()
    repo = tmp_path / "repo"
    proposed = repo / "ALT_SPEC" / "proposed_changes"
    proposed.mkdir(parents=True)
    (proposed / "README.md").write_text("index\n", encoding="utf-8")
    (proposed / "one.md").write_text("one\n", encoding="utf-8")
    (proposed / "two.md").write_text("two\n", encoding="utf-8")
    (repo / ".livespec.jsonc").write_text('{"spec_root": "ALT_SPEC"}\n', encoding="utf-8")

    result = module.resolve_plan_budget(repo=repo, work_items=[])

    assert result.proposed_changes_count == 2
    assert result.drainable_population == 2
