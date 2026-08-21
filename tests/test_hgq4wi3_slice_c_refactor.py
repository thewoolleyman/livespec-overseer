from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []

OWNER = "livespec-lloc-soft-band-owner: overseer-hgq4wi.3"


def test_hgq4wi3_slice_c_owner_markers_are_retired_after_cohesive_splits() -> None:
    root = Path(__file__).resolve().parents[1]
    overseer = root / "overseer"
    extracted = (
        "_supervisor_attention_observe",
        "_supervisor_discovery_adoption",
        "_supervisor_launch_profile_capture",
        "_supervisor_prompts_nudges",
    )
    for module_name in extracted:
        module_path = overseer / f"{module_name}.py"
        assert module_path.is_file(), module_path
        module = importlib.import_module(module_name)
        assert module.__all__

    owner_paths = (
        overseer / "_supervisor_attention.py",
        overseer / "_supervisor_discovery.py",
        overseer / "_supervisor_launch_profile.py",
        overseer / "_supervisor_prompts.py",
    )
    for path in owner_paths:
        assert OWNER not in path.read_text(encoding="utf-8")
