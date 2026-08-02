"""Tests for release-tier module-size decompositions."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_runtime_soft_band_files_are_split_by_named_concern():
    root = Path(__file__).resolve().parent.parent / "overseer"
    modules = [
        "_supervisor_attention_alerts",
        "_supervisor_evaluate_target",
        "_supervisor_pair_stall",
        "_supervisor_unindexed_codex",
        "codex_session_index",
    ]
    for name in modules:
        assert (root / f"{name}.py").is_file()
        assert importlib.import_module(name) is not None

    pair = importlib.import_module("_supervisor_pair")
    assert not hasattr(pair, "_try_pair_nudge")

    discovery_source = (root / "_supervisor_discovery.py").read_text(encoding="utf-8")
    assert "_unindexed_codex_rows(sup=sup" in discovery_source
