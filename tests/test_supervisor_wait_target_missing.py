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


def test_wait_target_source_routing_skips_non_fabro_and_defaults_unknown_remote(tmp_path):
    records = importlib.import_module("_supervisor_records")
    sources = importlib.import_module("_supervisor_wait_target_sources")

    non_fabro = sources.verify_wait_target_record(
        repo=tmp_path,
        record={"kind": "pr", "target_id": "123"},
        cache=None,
        now=1.0,
    )
    unknown = sources.verify_wait_target_record(
        repo=tmp_path,
        record={"kind": "fabro-run", "target_id": "remote-run"},
        cache=None,
        now=2.0,
    )

    assert non_fabro == records.WaitTargetCacheEntry(checked_at=1.0, status="present", note=None)
    assert unknown.note == "fabro-run remote-run absent from every mandatory leg"
