"""Structural checks for the overseer supervisor soft-band refactor."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(*, rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_supervisor_soft_band_debt_is_split_into_cohesive_modules():
    ready_module = ROOT / "overseer/_supervisor_ready_fresh.py"
    start_module = ROOT / "overseer/_supervisor_cli_start.py"

    assert ready_module.is_file()
    assert start_module.is_file()
    assert "_fresh_ready_without_round_valid" not in _source(
        rel_path="overseer/_supervisor_ready.py"
    )
    assert "_cmd_start" not in _source(rel_path="overseer/supervisor.py")


def test_supervisor_soft_band_markers_are_removed_from_package_and_mirror():
    owner = "livespec-lloc-soft-band-owner: overseer-hgq4wi.28"

    for rel_path in [
        "overseer/_supervisor_ready.py",
        "overseer/supervisor.py",
        ".claude-plugin/overseer/_supervisor_ready.py",
        ".claude-plugin/overseer/supervisor.py",
    ]:
        assert owner not in _source(rel_path=rel_path)
