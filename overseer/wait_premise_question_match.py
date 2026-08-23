"""Pure option/record matching for the foreman wait-premise question lint."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

__all__: list[str] = [
    "EvidenceChecker",
    "WaitPremiseIssue",
    "canonical_kind",
    "issue_for_option",
    "option_lines",
]

EvidenceChecker = Callable[..., bool | None]

_KIND_ALIASES = {
    "fabro run": "fabro-run",
    "fabro-run": "fabro-run",
    "pr": "pr",
    "ci run": "ci-run",
    "ci-run": "ci-run",
    "work item close": "work-item-close",
    "work-item-close": "work-item-close",
}
_OPTION_LINE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(?P<option>[^\n]+)", re.MULTILINE)
_EXPRESSIBLE_WAIT = re.compile(
    r"\bwait(?:ing)?\s+for\b[^\n]*?\b(?P<kind>"
    r"fabro[- ]run|pr|ci[- ]run|work[- ]item[- ]close"
    r")\b(?:\s+(?P<target>\S+))?",
    re.IGNORECASE,
)
_ANY_WAIT_FOR = re.compile(r"\bwait(?:ing)?\s+for\b", re.IGNORECASE)
_TYPED_WAIT_PREMISE = re.compile(
    r"\bwait-premise\s*:\s*"
    r"(?=[^\n]*(?:kind|target))"
    r"(?=[^\n]*\bkind\s*=\s*(?P<kind>fabro-run|pr|ci-run|work-item-close)\b)"
    r"(?=[^\n]*\btarget\s*=\s*(?P<target>\S+))",
    re.IGNORECASE,
)


@dataclass(frozen=True, kw_only=True)
class WaitPremiseIssue:
    """A surfaced wait-premise gap; never an instruction to suppress."""

    reason: str
    option: str
    kind: str | None = None
    target_id: str | None = None
    evidence_source: str | None = None


def option_lines(*, text: str) -> tuple[str, ...]:
    return tuple(match.group("option").strip() for match in _OPTION_LINE.finditer(text))


def issue_for_option(
    *,
    option: str,
    records: list[dict[str, object]],
    now: str,
    evidence_still_holds: EvidenceChecker | None,
) -> WaitPremiseIssue | None:
    if _ANY_WAIT_FOR.search(option) is None:
        return None
    typed = typed_premise(option=option)
    if typed is not None:
        return issue_for_typed_premise(
            option=option,
            records=records,
            now=now,
            evidence_still_holds=evidence_still_holds,
            kind=typed[0],
            target_id=typed[1],
        )
    wait = _EXPRESSIBLE_WAIT.search(option)
    if wait is None:
        return WaitPremiseIssue(reason="inexpressible-wait-kind", option=option)
    return WaitPremiseIssue(
        reason="missing-typed-premise",
        option=option,
        kind=canonical_kind(kind=wait.group("kind")),
        target_id=wait.group("target"),
    )


def issue_for_typed_premise(
    *,
    option: str,
    records: list[dict[str, object]],
    now: str,
    evidence_still_holds: EvidenceChecker | None,
    kind: str,
    target_id: str,
) -> WaitPremiseIssue | None:
    record = matching_record(records=records, kind=kind, target_id=target_id)
    if record is None:
        return WaitPremiseIssue(
            reason="missing-recorded-premise",
            option=option,
            kind=kind,
            target_id=target_id,
        )
    return recheck_issue(
        option=option,
        record=record,
        now=now,
        evidence_still_holds=evidence_still_holds,
    )


def typed_premise(*, option: str) -> tuple[str, str] | None:
    match = _TYPED_WAIT_PREMISE.search(option)
    if match is None:
        return None
    return match.group("kind").lower(), match.group("target").rstrip("),.")


def matching_record(
    *, records: list[dict[str, object]], kind: str, target_id: str
) -> dict[str, object] | None:
    for record in records:
        if record.get("kind") == kind and record.get("target_id") == target_id:
            return record
    return None


def recheck_issue(
    *,
    option: str,
    record: dict[str, object],
    now: str,
    evidence_still_holds: EvidenceChecker | None,
) -> WaitPremiseIssue | None:
    if not recheck_due(now=now, recheck_by=str(record["recheck_by"])):
        return None
    if evidence_still_holds is None:
        return issue_from_record(reason="premise-recheck-untestable", option=option, record=record)
    result = evidence_still_holds(record=record)
    if result is True:
        return None
    if result is False:
        return issue_from_record(reason="premise-recheck-failed", option=option, record=record)
    return issue_from_record(reason="premise-recheck-untestable", option=option, record=record)


def recheck_due(*, now: str, recheck_by: str) -> bool:
    return timestamp(value=now) >= timestamp(value=recheck_by)


def timestamp(*, value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def issue_from_record(*, reason: str, option: str, record: dict[str, object]) -> WaitPremiseIssue:
    return WaitPremiseIssue(
        reason=reason,
        option=option,
        kind=str(record["kind"]),
        target_id=str(record["target_id"]),
        evidence_source=str(record["evidence_source"]),
    )


def canonical_kind(*, kind: str) -> str:
    return _KIND_ALIASES[kind.lower().replace("-", " ")]
