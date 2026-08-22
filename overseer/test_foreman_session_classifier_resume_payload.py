"""Beside-tests for the foreman's deterministic session-lifecycle classifier."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_foreman_session_classifier_exact_resume_payload():
    module_path = Path(__file__).with_name("foreman_session_classifier.py")
    assert module_path.is_file()
    classifier = importlib.import_module("foreman_session_classifier")

    coords = classifier.SessionCoordinates(
        repo="/data/projects/livespec-overseer",
        topic="foreman",
        session_name="livespec-overseer-foreman",
    )
    exact_index = classifier.IndexedSessionEvidence(
        runtime="codex",
        repo=None,
        session_name="livespec-overseer-foreman",
        session_id="019fc11c-68c4-78c3-824b-d9b97de55a78",
        transcript_path="/home/me/.codex/sessions/2026/08/03/rollout.jsonl",
    )

    resume_decision = classifier.classify_session_lifecycle(
        coordinates=coords,
        snapshot=classifier.SnapshotEvidence(
            status="session-gone",
            runtime="codex",
            session_identity="codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
        ),
        live_sessions=(),
        indexed_sessions=(exact_index,),
    )
    assert resume_decision.resume == classifier.ResumeEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        topic="foreman",
        session_name="livespec-overseer-foreman",
        session_id="019fc11c-68c4-78c3-824b-d9b97de55a78",
        transcript_path="/home/me/.codex/sessions/2026/08/03/rollout.jsonl",
    )
