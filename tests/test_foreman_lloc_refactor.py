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
