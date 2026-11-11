"""Regression coverage for the aggregate purity-declaration inventory."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_ROOT = Path(__file__).resolve().parents[1]
_JUSTFILE = _ROOT / "justfile"
_INVENTORY = _ROOT / "check-targets.txt"


def _aggregate_targets() -> tuple[str, ...]:
    in_targets = False
    targets: list[str] = []
    for raw_line in _JUSTFILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "targets=(":
            in_targets = True
            continue
        if in_targets and line == ")":
            break
        if in_targets and line.startswith("check-"):
            targets.append(line.split(maxsplit=1)[0])
    return tuple(targets)


def _inventory_targets() -> tuple[str, ...]:
    return tuple(
        line.split(maxsplit=1)[0]
        for raw_line in _INVENTORY.read_text(encoding="utf-8").splitlines()
        if (line := raw_line.strip()).startswith("check-")
    )


def test_check_target_inventory_matches_check_aggregate() -> None:
    assert _INVENTORY.is_file()
    assert _inventory_targets() == _aggregate_targets()
