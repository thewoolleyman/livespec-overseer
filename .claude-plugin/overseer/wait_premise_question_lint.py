"""Fail-soft lint for foreman questions that offer typed waits."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import wait_premises
from wait_premise_question_match import (
    EvidenceChecker,
    WaitPremiseIssue,
    issue_for_option,
    option_lines,
)

__all__: list[str] = [
    "EvidenceChecker",
    "WaitPremiseIssue",
    "WaitPremiseQuestionReport",
    "WaitPremiseWriteReport",
    "lint_foreman_wait_question",
    "record_foreman_wait_premise",
]

_FOREMAN_TOPIC = "foreman"


@dataclass(frozen=True, kw_only=True)
class WaitPremiseQuestionReport:
    """Lint result for one foreman-authored question."""

    can_raise_question: bool
    issues: tuple[WaitPremiseIssue, ...]


@dataclass(frozen=True, kw_only=True)
class WaitPremiseWriteReport:
    """Outcome of trying to write the premise before raising a question."""

    can_raise_question: bool
    path: Path | None
    issues: tuple[WaitPremiseIssue, ...]


def record_foreman_wait_premise(
    *,
    repo: str | os.PathLike[str],
    kind: str,
    target_id: str,
    evidence_source: str,
    recorded_at: str,
    recheck_by: str,
) -> WaitPremiseWriteReport:
    try:
        path = wait_premises.write_wait_premise(
            repo=repo,
            topic=_FOREMAN_TOPIC,
            kind=kind,
            target_id=target_id,
            evidence_source=evidence_source,
            recorded_at=recorded_at,
            recheck_by=recheck_by,
        )
    except (OSError, ValueError) as error:
        return WaitPremiseWriteReport(
            can_raise_question=True,
            path=None,
            issues=(
                WaitPremiseIssue(
                    reason="premise-write-failed",
                    option="",
                    kind=kind,
                    target_id=target_id,
                    evidence_source=str(error),
                ),
            ),
        )
    return WaitPremiseWriteReport(can_raise_question=True, path=path, issues=())


def lint_foreman_wait_question(
    *,
    text: str,
    repo: str | os.PathLike[str],
    now: str,
    evidence_still_holds: EvidenceChecker | None = None,
) -> WaitPremiseQuestionReport:
    records = wait_premises.read_wait_premises(repo=repo, topic=_FOREMAN_TOPIC)
    issues: list[WaitPremiseIssue] = []
    for option in option_lines(text=text):
        issue = issue_for_option(
            option=option,
            records=records,
            now=now,
            evidence_still_holds=evidence_still_holds,
        )
        if issue is not None:
            issues.append(issue)
    return WaitPremiseQuestionReport(can_raise_question=True, issues=tuple(issues))
