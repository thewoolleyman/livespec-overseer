"""Metadata-shape coverage for the parent finalization guard."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"


def finalizer_module():
    """Import the runtime finalizer module from the governed carrier."""
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("parent_child_feature_finalizer")


def test_direct_parent_acceptance_criteria_authorizes_terminal_children():
    """A direct criteria field is sufficient without metadata."""
    decision = finalizer_module().completed_feature_parent_route(
        parent={
            "id": "overseer-pfpfty",
            "issue_type": "feature",
            "acceptance_criteria": "All direct children are merged.",
        },
        children=[{"id": "overseer-pfpfty.1", "status": "closed"}],
    )

    assert decision.authorized is True


@pytest.mark.parametrize("metadata", [None, "malformed"])
def test_missing_or_malformed_metadata_cannot_authorize(metadata: object):
    """Missing criteria stays ineligible rather than assuming metadata shape."""
    parent = {"id": "overseer-pfpfty", "issue_type": "feature"}
    if metadata is not None:
        parent["metadata"] = metadata

    decision = finalizer_module().completed_feature_parent_route(
        parent=parent,
        children=[{"id": "overseer-pfpfty.1", "status": "closed"}],
    )

    assert decision.authorized is False
    assert "acceptance criteria: <missing>" in decision.audit_note
