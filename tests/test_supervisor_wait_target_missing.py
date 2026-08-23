"""Repo-level mirror for wait-target-missing attention wiring."""

from __future__ import annotations

import importlib

__all__: list[str] = []


def test_wait_target_missing_is_a_needs_you_attention_status():
    view = importlib.import_module("_supervisor_view")
    wait_target = importlib.import_module("_supervisor_wait_target")

    assert wait_target.WAIT_TARGET_MISSING_STATUS in view.ATTENTION_STATUSES
    assert (
        wait_target.WAIT_TARGET_MISSING_STATUS
        == wait_target.WAIT_TARGET_MISSING_CONDITION
        == "wait-target-missing"
    )
