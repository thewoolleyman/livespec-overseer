"""Repo-level mirror for the foreman session classifier edge beside-tests."""

from __future__ import annotations

from overseer import test_foreman_session_classifier_edges as beside

__all__: list[str] = []


def test_foreman_session_classifier_reports_live_and_index_edge_cases():
    beside.test_foreman_session_classifier_reports_live_and_index_edge_cases()


def test_foreman_session_classifier_reports_conflicting_runtime_and_index_evidence():
    beside.test_foreman_session_classifier_reports_conflicting_runtime_and_index_evidence()
