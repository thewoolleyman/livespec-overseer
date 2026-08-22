"""Scanner for live plan handoff files forbidden by the Planning Lane."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = [
    "FORBIDDEN_LIVE_FILENAMES",
    "live_handoff_violations",
]

FORBIDDEN_LIVE_FILENAMES = ("handoff.md", "supervisor-handoff.md")


def _live_plan_directories(*, root: Path) -> list[Path]:
    plan_root = root / "plan"
    return sorted(
        child for child in plan_root.iterdir() if child.is_dir() and child.name != "archive"
    )


def live_handoff_violations(*, root: Path) -> tuple[int, list[Path]]:
    violations: list[Path] = []
    live_plans = _live_plan_directories(root=root)
    for plan_dir in live_plans:
        for filename in FORBIDDEN_LIVE_FILENAMES:
            candidate = plan_dir / filename
            if candidate.is_file():
                violations.append(candidate.relative_to(root))
    return len(live_plans), violations
