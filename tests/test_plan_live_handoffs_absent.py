"""Live plan directories must not carry mutable handoff files.

livespec SPECIFICATION/spec.md ratifies the Planning Lane rule that a plan
created after ratification MUST NOT create a live `handoff.md` or
`supervisor-handoff.md`. Pre-existing records may be preserved under
`plan/<slug>/research/`, and archived plans live under `plan/archive/`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCANNER_PATH = _REPO_ROOT / "scripts" / "plan_live_handoff_scan.py"


def _scanner_module() -> ModuleType:
    assert _SCANNER_PATH.is_file()
    spec = importlib.util.spec_from_file_location("plan_live_handoff_scan", _SCANNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scanner_discriminates_live_research_and_archive_handoffs(*, tmp_path: Path) -> None:
    """The synthetic control proves both the refusing and allowed directions."""
    scanner = _scanner_module()
    live_plan = tmp_path / "plan" / "live"
    live_plan.mkdir(parents=True)
    (live_plan / "handoff.md").write_text("forbidden\n", encoding="utf-8")
    (live_plan / "research").mkdir()
    (live_plan / "research" / "handoff.md").write_text("preserved\n", encoding="utf-8")
    archived_plan = tmp_path / "plan" / "archive" / "archived"
    archived_plan.mkdir(parents=True)
    (archived_plan / "handoff.md").write_text("archived\n", encoding="utf-8")

    live_count, violations = scanner.live_handoff_violations(root=tmp_path)

    assert live_count == 1
    assert violations == [Path("plan/live/handoff.md")]


def test_scanner_reports_both_forbidden_live_filenames(*, tmp_path: Path) -> None:
    scanner = _scanner_module()
    live_plan = tmp_path / "plan" / "live"
    live_plan.mkdir(parents=True)
    for filename in scanner.FORBIDDEN_LIVE_FILENAMES:
        (live_plan / filename).write_text("forbidden\n", encoding="utf-8")

    assert scanner.live_handoff_violations(root=tmp_path) == (
        1,
        [
            Path("plan/live/handoff.md"),
            Path("plan/live/supervisor-handoff.md"),
        ],
    )


def test_real_tree_has_no_live_plan_handoff_files() -> None:
    scanner = _scanner_module()
    live_count, violations = scanner.live_handoff_violations(root=_REPO_ROOT)

    assert live_count > 0
    assert violations == []
