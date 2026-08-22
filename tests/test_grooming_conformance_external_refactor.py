"""Regression coverage for the grooming-invariants external split."""

from __future__ import annotations

import importlib
from pathlib import Path

import grooming_conformance_invariants

__all__: list[str] = []


def test_externally_decided_invariants_are_extracted_to_their_own_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "overseer" / "grooming_conformance_external.py"

    assert module_path.is_file(), module_path
    module = importlib.import_module("grooming_conformance_external")
    assert module.__all__ == [
        "cross_repo_dependency_check",
        "routing_field_pending",
        "split_acceptance_label_pending",
    ]
    source = Path(grooming_conformance_invariants.__file__).read_text(encoding="utf-8")
    for name in module.__all__:
        assert f"def {name}" not in source, name


def test_the_split_is_mirrored_and_the_marker_is_discharged():
    root = Path(__file__).resolve().parents[1]
    for name in ("grooming_conformance_invariants.py", "grooming_conformance_external.py"):
        package = (root / "overseer" / name).read_text(encoding="utf-8")
        mirror = (root / ".claude-plugin" / "overseer" / name).read_text(encoding="utf-8")
        assert package == mirror, name
        assert "livespec-lloc-soft-band-owner" not in package, name
