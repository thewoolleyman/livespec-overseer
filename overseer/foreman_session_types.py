"""Typed foreman session-lifecycle evidence and result values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, TypeAlias

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
]

ForemanSessionAction: TypeAlias = Literal["exact_resume", "report_only", "start"]
ReportReason: TypeAlias = Literal[
    "already_live",
    "ambiguous_identity",
    "conflicting_evidence",
    "intentionally_unassigned",
    "missing_transcript",
    "relative_repo_refused",
    "stale_namesake",
    "tmux_session_occupied",
]

EXACT_RESUME: Final[ForemanSessionAction] = "exact_resume"
REPORT_ONLY: Final[ForemanSessionAction] = "report_only"
START: Final[ForemanSessionAction] = "start"
FOREMAN_SESSION_ACTIONS: Final[tuple[ForemanSessionAction, ...]] = (
    EXACT_RESUME,
    REPORT_ONLY,
    START,
)

ALREADY_LIVE: Final[ReportReason] = "already_live"
AMBIGUOUS_IDENTITY: Final[ReportReason] = "ambiguous_identity"
CONFLICTING_EVIDENCE: Final[ReportReason] = "conflicting_evidence"
INTENTIONALLY_UNASSIGNED: Final[ReportReason] = "intentionally_unassigned"
MISSING_TRANSCRIPT: Final[ReportReason] = "missing_transcript"
RELATIVE_REPO_REFUSED: Final[ReportReason] = "relative_repo_refused"
STALE_NAMESAKE: Final[ReportReason] = "stale_namesake"
TMUX_SESSION_OCCUPIED: Final[ReportReason] = "tmux_session_occupied"
REPORT_REASONS: Final[tuple[ReportReason, ...]] = (
    ALREADY_LIVE,
    AMBIGUOUS_IDENTITY,
    CONFLICTING_EVIDENCE,
    INTENTIONALLY_UNASSIGNED,
    MISSING_TRANSCRIPT,
    RELATIVE_REPO_REFUSED,
    STALE_NAMESAKE,
    TMUX_SESSION_OCCUPIED,
)


@dataclass(frozen=True, kw_only=True)
class SessionCoordinates:
    repo: str
    topic: str
    session_name: str


@dataclass(frozen=True, kw_only=True)
class SnapshotEvidence:
    status: str | None
    runtime: str | None
    session_identity: str | None


@dataclass(frozen=True, kw_only=True)
class LiveSessionEvidence:
    runtime: str
    repo: str
    session_name: str
    session_id: str


@dataclass(frozen=True, kw_only=True)
class IndexedSessionEvidence:
    runtime: str
    repo: str | None
    session_name: str
    session_id: str
    transcript_path: str | None


@dataclass(frozen=True, kw_only=True)
class StartEvidence:
    repo: str
    topic: str
    session_name: str


@dataclass(frozen=True, kw_only=True)
class ResumeEvidence:
    runtime: str
    repo: str
    topic: str
    session_name: str
    session_id: str
    transcript_path: str


@dataclass(frozen=True, kw_only=True)
class ReportEvidence:
    reason: ReportReason
    details: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class ForemanSessionDecision:
    action: ForemanSessionAction
    start: StartEvidence | None = None
    resume: ResumeEvidence | None = None
    report: ReportEvidence | None = None
