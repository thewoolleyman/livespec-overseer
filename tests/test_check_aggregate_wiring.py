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


def test_check_no_workflow_edits_is_reached_by_full_check() -> None:
    assert "check-no-workflow-edits" in _check_aggregate_targets()
