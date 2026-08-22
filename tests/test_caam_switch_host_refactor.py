"""Regression coverage for the caam switch host-boundary split."""

from __future__ import annotations

import importlib
from pathlib import Path

import caam_switch

__all__: list[str] = []


def test_host_boundary_is_extracted_to_a_cohesive_module():
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "_caam_switch_host.py"

    assert module_path.is_file(), module_path
    module = importlib.import_module("_caam_switch_host")
    assert module.__all__ == [
        "SwitchLock",
        "SwitchLockFactory",
        "acquire_switch_lock",
        "caam_activate",
    ]
    assert caam_switch.acquire_switch_lock is module.acquire_switch_lock
    assert caam_switch.caam_activate is module.caam_activate
    assert caam_switch.SwitchLock is module.SwitchLock
    assert caam_switch.SwitchLockFactory is module.SwitchLockFactory

    source = Path(caam_switch.__file__).read_text(encoding="utf-8")
    assert "def acquire_switch_lock" not in source
    assert "def caam_activate" not in source
    assert "import fcntl" not in source


def test_the_extracted_module_holds_the_uncoverable_half_and_caam_switch_holds_none_of_it():
    """The seam is the host boundary, and this is what makes that checkable.

    Every definition that moved touches the host -- an fcntl lock and a
    subprocess call -- and so carries `# pragma: no cover`. Asserting that
    `caam_switch` retains none of those pragmas is what stops a later split
    from being drawn somewhere convenient instead of somewhere meaningful.
    """
    overseer_dir = Path(__file__).resolve().parents[1] / "overseer"
    host = (overseer_dir / "_caam_switch_host.py").read_text(encoding="utf-8")
    switch = (overseer_dir / "caam_switch.py").read_text(encoding="utf-8")

    marked = [
        line.split("#")[0].strip()
        for line in host.splitlines()
        if "# pragma: no cover" in line and line.startswith(("class ", "def "))
    ]
    assert marked == [
        "class _FcntlSwitchLock:",
        "def acquire_switch_lock(*, lock_path: Path) -> SwitchLock | None:",
        "def caam_activate(",
    ]
    assert "# pragma: no cover" not in switch


def test_the_discharged_soft_band_marker_is_gone_from_both_trees():
    """The exemption is removed, not repointed.

    A marker naming a CLOSED work-item is what made this debt exempt and
    ownerless. Once the file is under the ceiling there is nothing left for an
    exemption to justify, so the correct end state is no marker at all.
    """
    root = Path(__file__).resolve().parents[1]
    for tree in ("overseer", ".claude-plugin/overseer"):
        text = (root / tree / "caam_switch.py").read_text(encoding="utf-8")
        assert "livespec-lloc-soft-band-owner" not in text, tree


def test_both_split_modules_are_byte_identical_across_the_two_trees():
    """The mirror is hand-maintained with no sync recipe, so a NEW module is
    exactly the case most likely to land in one tree and not the other."""
    root = Path(__file__).resolve().parents[1]
    for name in ("caam_switch.py", "_caam_switch_host.py"):
        source = (root / "overseer" / name).read_bytes()
        mirror = (root / ".claude-plugin" / "overseer" / name).read_bytes()
        assert source == mirror, name
