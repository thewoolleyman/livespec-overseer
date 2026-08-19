"""Beside-tests for the foreman's deterministic session-lifecycle classifier."""
# livespec-lloc-soft-band-owner: overseer-hgq4wi.6

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


def test_foreman_session_classifier_table():
    module_path = Path(__file__).with_name("foreman_session_classifier.py")
    assert module_path.is_file()
    classifier = importlib.import_module("foreman_session_classifier")

    coords = classifier.SessionCoordinates(
        repo="/data/projects/livespec-overseer",
        topic="foreman",
        session_name="livespec-overseer-foreman",
    )
    relative = classifier.SessionCoordinates(
        repo="relative/repo",
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
    no_transcript = classifier.IndexedSessionEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        session_name="livespec-overseer-foreman",
        session_id="019fc11c-68c4-78c3-824b-d9b97de55a78",
        transcript_path=None,
    )
    stale_live = classifier.LiveSessionEvidence(
        runtime="codex",
        repo="/data/projects/other",
        session_name="livespec-overseer-foreman",
        session_id="019fc11c-68c4-78c3-824b-d9b97de55a78",
    )
    duplicate = classifier.IndexedSessionEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        session_name="livespec-overseer-foreman",
        session_id="119fc11c-68c4-78c3-824b-d9b97de55a78",
        transcript_path="/home/me/.codex/sessions/2026/08/03/other.jsonl",
    )
    other_live = classifier.LiveSessionEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        session_name="other-session",
        session_id="219fc11c-68c4-78c3-824b-d9b97de55a78",
    )
    other_index = classifier.IndexedSessionEvidence(
        runtime="codex",
        repo="/data/projects/livespec-overseer",
        session_name="other-session",
        session_id="219fc11c-68c4-78c3-824b-d9b97de55a78",
        transcript_path="/home/me/.codex/sessions/2026/08/03/ignored.jsonl",
    )

    cases = [
        (
            "never-started",
            coords,
            classifier.SnapshotEvidence(
                status="session-gone",
                runtime="codex",
                session_identity="none:/data/projects/livespec-overseer:foreman",
            ),
            (other_live,),
            (other_index,),
            classifier.START,
            None,
        ),
        (
            "exact crashed resume",
            coords,
            classifier.SnapshotEvidence(
                status="session-gone",
                runtime="codex",
                session_identity="codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
            ),
            (),
            (exact_index,),
            classifier.EXACT_RESUME,
            None,
        ),
        (
            "intentionally unassigned",
            coords,
            classifier.SnapshotEvidence(status="unassigned", runtime=None, session_identity=None),
            (),
            (),
            classifier.REPORT_ONLY,
            classifier.INTENTIONALLY_UNASSIGNED,
        ),
        (
            "missing transcript",
            coords,
            classifier.SnapshotEvidence(
                status="session-gone",
                runtime="codex",
                session_identity="codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
            ),
            (),
            (no_transcript,),
            classifier.REPORT_ONLY,
            classifier.MISSING_TRANSCRIPT,
        ),
        (
            "stale namesake",
            coords,
            classifier.SnapshotEvidence(
                status="session-gone",
                runtime="codex",
                session_identity="none:/data/projects/livespec-overseer:foreman",
            ),
            (stale_live,),
            (),
            classifier.REPORT_ONLY,
            classifier.STALE_NAMESAKE,
        ),
        (
            "duplicate identity",
            coords,
            classifier.SnapshotEvidence(
                status="session-gone",
                runtime="codex",
                session_identity="codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
            ),
            (),
            (exact_index, duplicate),
            classifier.REPORT_ONLY,
            classifier.AMBIGUOUS_IDENTITY,
        ),
        (
            "relative repo refusal",
            relative,
            classifier.SnapshotEvidence(
                status="session-gone", runtime="codex", session_identity=None
            ),
            (),
            (),
            classifier.REPORT_ONLY,
            classifier.RELATIVE_REPO_REFUSED,
        ),
    ]

    for name, case_coords, snapshot, live, indexed, action, reason in cases:
        decision = classifier.classify_session_lifecycle(
            coordinates=case_coords,
            snapshot=snapshot,
            live_sessions=live,
            indexed_sessions=indexed,
        )
        assert decision.action == action, name
        if reason is not None:
            assert decision.report is not None, name
            assert decision.report.reason == reason, name

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
