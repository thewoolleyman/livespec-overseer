"""Tests for the completed parent-child feature finalization guard."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "parent_child_feature_finalizer.py"


def finalizer_module():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("parent_child_feature_finalizer")


def test_completed_feature_parent_gets_a_real_bd_finalization_route():
    mod = finalizer_module()

    decision = mod.completed_feature_parent_route(
        parent={
            "id": "overseer-pfpfty",
            "issue_type": "feature",
            "metadata": {"acceptance_criteria": "All child slices are merged."},
        },
        children=[
            {"id": "overseer-pfpfty.1", "status": "closed"},
            {"id": "overseer-pfpfty.2", "status": "done"},
        ],
    )

    assert decision.authorized is True
    assert decision.commands == (
        "bd update overseer-pfpfty --type epic --append-notes <audit-note>",
        "bd epic close-eligible --dry-run",
        "bd epic close-eligible",
        "bd show overseer-pfpfty --json",
    )
    assert "All child slices are merged." in decision.audit_note


def test_feature_parent_route_rejects_an_open_direct_child():
    mod = finalizer_module()

    decision = mod.completed_feature_parent_route(
        parent={
            "id": "overseer-pfpfty",
            "issue_type": "feature",
            "metadata": {"acceptance_criteria": "All child slices are merged."},
        },
        children=[
            {"id": "overseer-pfpfty.1", "status": "closed"},
            {"id": "overseer-pfpfty.2", "status": "ready"},
        ],
    )

    assert decision.authorized is False
    assert decision.non_terminal_children == ("overseer-pfpfty.2",)
