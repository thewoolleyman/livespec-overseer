"""Deterministic foreman session-lifecycle classification."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from foreman_session_types import (
    ALREADY_LIVE,
    AMBIGUOUS_IDENTITY,
    CONFLICTING_EVIDENCE,
    EXACT_RESUME,
    FOREMAN_SESSION_ACTIONS,
    INTENTIONALLY_UNASSIGNED,
    MISSING_TRANSCRIPT,
    RELATIVE_REPO_REFUSED,
    REPORT_ONLY,
    REPORT_REASONS,
    STALE_NAMESAKE,
    START,
    TMUX_SESSION_OCCUPIED,
    ForemanSessionAction,
    ForemanSessionDecision,
    IndexedSessionEvidence,
    LiveSessionEvidence,
    ReportEvidence,
    ReportReason,
    ResumeEvidence,
    SessionCoordinates,
    SnapshotEvidence,
    StartEvidence,
)

__all__: list[str] = [
    "ALREADY_LIVE",
    "AMBIGUOUS_IDENTITY",
    "CONFLICTING_EVIDENCE",
    "EXACT_RESUME",
    "FOREMAN_SESSION_ACTIONS",
    "INTENTIONALLY_UNASSIGNED",
    "MISSING_TRANSCRIPT",
    "RELATIVE_REPO_REFUSED",
    "REPORT_ONLY",
    "REPORT_REASONS",
    "STALE_NAMESAKE",
    "START",
    "TMUX_SESSION_OCCUPIED",
    "ForemanSessionAction",
    "ForemanSessionDecision",
    "IndexedSessionEvidence",
    "LiveSessionEvidence",
    "ReportEvidence",
    "ReportReason",
    "ResumeEvidence",
    "SessionCoordinates",
    "SnapshotEvidence",
    "StartEvidence",
    "classify_session_lifecycle",
]


def _repo_key(*, repo: str) -> str:
    return os.path.normpath(repo)


def _same_repo(*, candidate: str | None, repo: str) -> bool:
    return candidate is None or _repo_key(repo=candidate) == _repo_key(repo=repo)


def _snapshot_session_id(*, snapshot: SnapshotEvidence) -> str | None:
    prefix = "codex:"
    identity = snapshot.session_identity
    if identity is None or not identity.startswith(prefix):
        return None
    session_id = identity.removeprefix(prefix)
    return session_id if session_id else None


def _report(*, reason: ReportReason, details: tuple[str, ...] = ()) -> ForemanSessionDecision:
    return ForemanSessionDecision(
        action=REPORT_ONLY,
        report=ReportEvidence(reason=reason, details=details),
    )


def _start(*, coordinates: SessionCoordinates) -> ForemanSessionDecision:
    return ForemanSessionDecision(
        action=START,
        start=StartEvidence(
            repo=coordinates.repo,
            topic=coordinates.topic,
            session_name=coordinates.session_name,
        ),
    )


def _resume(
    *, coordinates: SessionCoordinates, evidence: IndexedSessionEvidence
) -> ForemanSessionDecision:
    transcript_path = evidence.transcript_path
    if transcript_path is None:
        return _report(reason=MISSING_TRANSCRIPT, details=(evidence.session_id,))
    return ForemanSessionDecision(
        action=EXACT_RESUME,
        resume=ResumeEvidence(
            runtime=evidence.runtime,
            repo=coordinates.repo,
            topic=coordinates.topic,
            session_name=coordinates.session_name,
            session_id=evidence.session_id,
            transcript_path=transcript_path,
        ),
    )


def _matching_live(
    *, coordinates: SessionCoordinates, live_sessions: Sequence[LiveSessionEvidence]
) -> tuple[list[LiveSessionEvidence], list[LiveSessionEvidence]]:
    exact: list[LiveSessionEvidence] = []
    stale: list[LiveSessionEvidence] = []
    for session in live_sessions:
        if session.session_name != coordinates.session_name:
            continue
        if _same_repo(candidate=session.repo, repo=coordinates.repo):
            exact.append(session)
        else:
            stale.append(session)
    return exact, stale


def _matching_index(
    *, coordinates: SessionCoordinates, indexed_sessions: Sequence[IndexedSessionEvidence]
) -> tuple[list[IndexedSessionEvidence], list[IndexedSessionEvidence]]:
    exact: list[IndexedSessionEvidence] = []
    stale: list[IndexedSessionEvidence] = []
    for session in indexed_sessions:
        if session.session_name != coordinates.session_name:
            continue
        if _same_repo(candidate=session.repo, repo=coordinates.repo):
            exact.append(session)
        else:
            stale.append(session)
    return exact, stale


def _unique_ids(*, sessions: Sequence[LiveSessionEvidence | IndexedSessionEvidence]) -> set[str]:
    return {session.session_id for session in sessions}


def _classify_no_index(
    *, coordinates: SessionCoordinates, expected_id: str | None
) -> ForemanSessionDecision:
    if expected_id is not None:
        return _report(reason=MISSING_TRANSCRIPT, details=(expected_id,))
    return _start(coordinates=coordinates)


def _classify_indexed(
    *,
    coordinates: SessionCoordinates,
    indexed: IndexedSessionEvidence,
    expected_id: str | None,
) -> ForemanSessionDecision:
    if expected_id is not None and indexed.session_id != expected_id:
        return _report(
            reason=CONFLICTING_EVIDENCE,
            details=(expected_id, indexed.session_id),
        )
    return _resume(coordinates=coordinates, evidence=indexed)


def _live_report(
    *, live_exact: Sequence[LiveSessionEvidence], live_stale: Sequence[LiveSessionEvidence]
) -> ForemanSessionDecision | None:
    if len(live_exact) > 1 or len(_unique_ids(sessions=live_exact)) > 1:
        return _report(reason=AMBIGUOUS_IDENTITY)
    if live_exact:
        return _report(reason=ALREADY_LIVE, details=(live_exact[0].session_id,))
    if live_stale:
        return _report(reason=STALE_NAMESAKE)
    return None


def _classify_absolute(
    *,
    coordinates: SessionCoordinates,
    snapshot: SnapshotEvidence,
    live_sessions: Sequence[LiveSessionEvidence],
    indexed_sessions: Sequence[IndexedSessionEvidence],
    occupied_tmux_sessions: Sequence[str],
) -> ForemanSessionDecision:
    preflight = _absolute_preflight_report(
        coordinates=coordinates,
        snapshot=snapshot,
        occupied_tmux_sessions=occupied_tmux_sessions,
    )
    if preflight is not None:
        return preflight

    live_exact, live_stale = _matching_live(coordinates=coordinates, live_sessions=live_sessions)
    indexed_exact, indexed_stale = _matching_index(
        coordinates=coordinates, indexed_sessions=indexed_sessions
    )
    live_decision = _live_report(live_exact=live_exact, live_stale=live_stale)
    if live_decision is not None:
        return live_decision
    if indexed_stale:
        return _report(reason=STALE_NAMESAKE)
    if len(indexed_exact) > 1 or len(_unique_ids(sessions=indexed_exact)) > 1:
        return _report(reason=AMBIGUOUS_IDENTITY)

    expected_id = _snapshot_session_id(snapshot=snapshot)
    if not indexed_exact:
        return _classify_no_index(coordinates=coordinates, expected_id=expected_id)
    return _classify_indexed(
        coordinates=coordinates,
        indexed=indexed_exact[0],
        expected_id=expected_id,
    )


def _absolute_preflight_report(
    *,
    coordinates: SessionCoordinates,
    snapshot: SnapshotEvidence,
    occupied_tmux_sessions: Sequence[str],
) -> ForemanSessionDecision | None:
    if snapshot.status == "unassigned":
        return _report(reason=INTENTIONALLY_UNASSIGNED)
    if coordinates.session_name in occupied_tmux_sessions:
        return _report(reason=TMUX_SESSION_OCCUPIED, details=(coordinates.session_name,))
    return None


def classify_session_lifecycle(
    *,
    coordinates: SessionCoordinates,
    snapshot: SnapshotEvidence,
    live_sessions: Sequence[LiveSessionEvidence],
    indexed_sessions: Sequence[IndexedSessionEvidence],
    occupied_tmux_sessions: Sequence[str] = (),
) -> ForemanSessionDecision:
    """Classify a foreman lifecycle act from exact runtime/index evidence.

    The classifier returns only a closed action id plus typed evidence. It never emits
    a shell command, and it treats every ambiguity as report-only so the caller cannot
    guess which session to launch or resume.
    """
    if not Path(coordinates.repo).is_absolute():
        return _report(reason=RELATIVE_REPO_REFUSED, details=(coordinates.repo,))
    return _classify_absolute(
        coordinates=coordinates,
        snapshot=snapshot,
        live_sessions=live_sessions,
        indexed_sessions=indexed_sessions,
        occupied_tmux_sessions=occupied_tmux_sessions,
    )
