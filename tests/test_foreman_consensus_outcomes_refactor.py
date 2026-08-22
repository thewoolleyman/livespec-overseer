"""Regression coverage for the consensus outcome-payload split."""

from __future__ import annotations

import importlib
from pathlib import Path

import foreman_consensus_decision

__all__: list[str] = []


def test_outcome_payloads_are_extracted_to_a_cohesive_module():
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "foreman_consensus_outcomes.py"

    assert module_path.is_file(), module_path
    module = importlib.import_module("foreman_consensus_outcomes")
    assert module.__all__ == [
        "dissent_result",
        "escalation",
        "held_reviewer_ids",
        "majority",
        "minority_override",
        "unanimous",
    ]
    assert foreman_consensus_decision.escalation is module.escalation
    source = Path(foreman_consensus_decision.__file__).read_text(encoding="utf-8")
    assert "def escalation" not in source
    assert "def minority_override" not in source


def test_the_dead_soft_band_marker_is_discharged_not_retargeted():
    root = Path(__file__).resolve().parents[1]
    for tree in ("overseer", ".claude-plugin/overseer"):
        body = (root / tree / "foreman_consensus_decision.py").read_text(encoding="utf-8")
        assert "livespec-lloc-soft-band-owner" not in body, tree
