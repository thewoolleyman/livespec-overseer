"""Deterministic foreman session-lifecycle classification."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from foreman_session_lifecycle import classify_absolute_session
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


def _report(*, reason: ReportReason, details: tuple[str, ...] = ()) -> ForemanSessionDecision:
    return ForemanSessionDecision(
        action=REPORT_ONLY,
        report=ReportEvidence(reason=reason, details=details),
    )


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
    return classify_absolute_session(
        coordinates=coordinates,
        snapshot=snapshot,
        live_sessions=live_sessions,
        indexed_sessions=indexed_sessions,
        occupied_tmux_sessions=occupied_tmux_sessions,
    )
