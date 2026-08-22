"""Beside-tests for the foreman session classifier's public result surface."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_foreman_session_classifier_is_a_closed_typed_result_surface():
    module_path = Path(__file__).with_name("foreman_session_classifier.py")
    assert module_path.is_file()
    classifier = importlib.import_module("foreman_session_classifier")

    assert classifier.FOREMAN_SESSION_ACTIONS == ("exact_resume", "report_only", "start")

    coords = classifier.SessionCoordinates(
        repo="/data/projects/livespec-overseer",
        topic="foreman",
        session_name="livespec-overseer-foreman",
    )
    decision = classifier.classify_session_lifecycle(
        coordinates=coords,
        snapshot=classifier.SnapshotEvidence(
            status="session-gone",
            runtime="codex",
            session_identity="none:/data/projects/livespec-overseer:foreman",
        ),
        live_sessions=(),
        indexed_sessions=(),
    )

    assert decision.action == classifier.START
    assert decision.start == classifier.StartEvidence(
        repo="/data/projects/livespec-overseer",
        topic="foreman",
        session_name="livespec-overseer-foreman",
    )
    assert decision.resume is None
    assert decision.report is None
