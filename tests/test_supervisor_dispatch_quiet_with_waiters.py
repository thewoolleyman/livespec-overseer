"""Repo-level mirror for aggregate dispatch-quiet-with-waiters wiring."""

from __future__ import annotations

import importlib

__all__: list[str] = []


def test_dispatch_quiet_with_waiters_is_a_single_attention_status():
    view = importlib.import_module("_supervisor_view")

    assert "dispatch-quiet-with-waiters" in view.ATTENTION_STATUSES
    assert view.ATTENTION_STATUSES.count("dispatch-quiet-with-waiters") == 1
