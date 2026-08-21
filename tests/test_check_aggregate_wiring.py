"""Coverage for repo-local gates wired into the full check aggregate."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[1]
_JUSTFILE = _REPO_ROOT / "justfile"


def _check_aggregate_targets() -> list[str]:
    justfile = _JUSTFILE.read_text(encoding="utf-8")
    start = justfile.index("    targets=(\n")
    end = justfile.index("    )", start)
    targets_block = justfile[start:end]
    return [
        line.strip() for line in targets_block.splitlines() if line.strip().startswith("check-")
    ]


def _check_aggregate_body() -> str:
    justfile = _JUSTFILE.read_text(encoding="utf-8")
    start = justfile.index("check:\n")
    end = justfile.index("# ---------------------------------------------------------------", start)
    return justfile[start:end]


def test_check_no_workflow_edits_is_reached_by_full_check() -> None:
    assert "check-no-workflow-edits" in _check_aggregate_targets()


def test_check_coverage_runs_after_per_file_coverage_produces_data() -> None:
    targets = _check_aggregate_targets()

    assert targets.index("check-per-file-coverage") < targets.index("check-coverage")


def test_check_aggregate_has_no_pre_coverage_consumer_hook() -> None:
    aggregate_body = _check_aggregate_body()

    assert "prep for check-per-file-coverage" not in aggregate_body
    assert "just check-coverage" not in aggregate_body
