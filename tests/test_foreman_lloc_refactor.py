from __future__ import annotations

import importlib
from pathlib import Path

OWNER = "livespec-lloc-soft-band-owner: overseer-hgq4wi.4"


def test_foreman_hgq4wi4_owner_markers_are_retired_after_cohesive_splits():
    root = Path(__file__).resolve().parents[1]
    overseer = root / "overseer"
    extracted = (
        "foreman_consensus_actions",
        "foreman_act_dispatch_result",
        "foreman_consensus_decision",
        "foreman_panel_refusal",
        "foreman_session_lifecycle",
        "foreman_work_item_session_store",
    )
    for module_name in extracted:
        module_path = overseer / f"{module_name}.py"
        assert module_path.is_file(), module_path
        module = importlib.import_module(module_name)
        assert module.__all__

    owner_paths = (
        overseer / "foreman_act_dispatch.py",
        overseer / "foreman_consensus_eval.py",
        overseer / "foreman_gather_collect.py",
        overseer / "foreman_panel.py",
        overseer / "foreman_session_classifier.py",
        overseer / "foreman_work_item_sessions.py",
    )
    for path in owner_paths:
        assert OWNER not in path.read_text(encoding="utf-8")


def test_foreman_e698_owner_markers_are_retired_after_policy_and_valve_splits():
    root = Path(__file__).resolve().parents[1]
    overseer = root / "overseer"
    extracted = {
        "foreman_act_valve": ("act_with_human_valve",),
        "foreman_runtime_policy": ("exit_reason", "stable_ticks"),
    }
    for module_name, public_names in extracted.items():
        module_path = overseer / f"{module_name}.py"
        assert module_path.is_file(), module_path
        module = importlib.import_module(module_name)
        assert module.__all__ == list(public_names)

    foreman_act = importlib.import_module("foreman_act")
    foreman_runtime = importlib.import_module("foreman_runtime")
    assert not hasattr(foreman_act, "_act_validated")
    assert not hasattr(foreman_runtime.ForemanRuntime, "_stable_ticks")
    assert not hasattr(foreman_runtime.ForemanRuntime, "_exit_reason")

    owner = "livespec-lloc-soft-band-owner: overseer-e698"
    for path in (overseer / "foreman_act.py", overseer / "foreman_runtime.py"):
        assert owner not in path.read_text(encoding="utf-8")


def test_foreman_act_consensus_record_helpers_are_extracted():
    root = Path(__file__).resolve().parents[1]
    overseer = root / "overseer"
    module_path = overseer / "foreman_act_consensus_record.py"

    assert module_path.is_file(), module_path
    extracted = importlib.import_module("foreman_act_consensus_record")
    assert extracted.__all__ == [
        "consensus_audit_record",
        "prepare_recorded_next_action",
    ]

    consensus = importlib.import_module("foreman_act_consensus")
    assert not hasattr(consensus, "_audit_record")
    assert not hasattr(consensus, "_recorded_next_action_record")
    assert not hasattr(consensus, "_prepare_recorded_next_action")
