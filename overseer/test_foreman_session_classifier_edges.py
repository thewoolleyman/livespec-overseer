"""Edge-case beside-tests for foreman session classification."""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []


def test_foreman_session_classifier_reports_live_and_index_edge_cases():
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
    live_exact = classifier.LiveSessionEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        session_name="livespec-overseer-foreman",
        session_id="019fc11c-68c4-78c3-824b-d9b97de55a78",
    )
    live_duplicate = classifier.LiveSessionEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        session_name="livespec-overseer-foreman",
        session_id="119fc11c-68c4-78c3-824b-d9b97de55a78",
    )
    stale_index = classifier.IndexedSessionEvidence(
        runtime="codex",
        repo="/data/projects/other",
        session_name="livespec-overseer-foreman",
        session_id="319fc11c-68c4-78c3-824b-d9b97de55a78",
        transcript_path="/home/me/.codex/sessions/2026/08/03/stale.jsonl",
    )

    cases = [
        (
            "snapshot identity but no index",
            (),
            (),
            classifier.MISSING_TRANSCRIPT,
        ),
        (
            "already live",
            (live_exact,),
            (exact_index,),
            classifier.ALREADY_LIVE,
        ),
        (
            "duplicate live identity",
            (live_exact, live_duplicate),
            (exact_index,),
            classifier.AMBIGUOUS_IDENTITY,
        ),
        (
            "stale indexed namesake",
            (),
            (stale_index,),
            classifier.STALE_NAMESAKE,
        ),
    ]

    for name, live, indexed, reason in cases:
        decision = classifier.classify_session_lifecycle(
            coordinates=coords,
            snapshot=classifier.SnapshotEvidence(
                status="session-gone",
                runtime="codex",
                session_identity="codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
            ),
            live_sessions=live,
            indexed_sessions=indexed,
        )

        assert decision.action == classifier.REPORT_ONLY, name
        assert decision.report is not None, name
        assert decision.report.reason == reason, name


def test_foreman_session_classifier_reports_conflicting_runtime_and_index_evidence():
    module_path = Path(__file__).with_name("foreman_session_classifier.py")
    assert module_path.is_file()
    classifier = importlib.import_module("foreman_session_classifier")

    decision = classifier.classify_session_lifecycle(
        coordinates=classifier.SessionCoordinates(
            repo="/data/projects/livespec-overseer",
            topic="foreman",
            session_name="livespec-overseer-foreman",
        ),
        snapshot=classifier.SnapshotEvidence(
            status="session-gone",
            runtime="codex",
            session_identity="codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
        ),
        live_sessions=(),
        indexed_sessions=(
            classifier.IndexedSessionEvidence(
                runtime="codex",
                repo="/data/projects/livespec-overseer",
                session_name="livespec-overseer-foreman",
                session_id="119fc11c-68c4-78c3-824b-d9b97de55a78",
                transcript_path="/home/me/.codex/sessions/2026/08/03/other.jsonl",
            ),
        ),
    )

    assert decision.action == classifier.REPORT_ONLY
    assert decision.report is not None
    assert decision.report.reason == classifier.CONFLICTING_EVIDENCE
