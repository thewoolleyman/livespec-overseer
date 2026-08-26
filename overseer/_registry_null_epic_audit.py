"""Raw mapping-store audit for rows with no recorded epic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from _registry_rows_io import read_row_records
from _registry_write_validation import persisted_projection

__all__: list[str] = [
    "NullEpicAuditRow",
    "audit_null_epics",
]

NullEpicAuditStatus = Literal["documented-null", "undocumented-null", "persisted-projection"]
EPIC_NULL_AUDIT_KEY = "epic_null_audit"


@dataclass(frozen=True, kw_only=True)
class NullEpicAuditRow:
    repo: str
    topic: str
    lineno: int
    status: NullEpicAuditStatus
    evidence: str | None


def _audit_evidence(*, row: dict[str, object]) -> str | None:
    evidence = row.get(EPIC_NULL_AUDIT_KEY)
    if isinstance(evidence, str) and evidence.strip():
        return evidence
    return None


def _audit_status(*, row: dict[str, object], evidence: str | None) -> NullEpicAuditStatus | None:
    """Classify one raw row, or None when it genuinely records an epic.

    A row carrying a persisted read-time placeholder has NO recorded epic — the
    durable-key contract requires it to be treated exactly as an absent one — so it
    is REPORTED rather than skipped. Keying only on absence is what let such a row
    sit unresolvable in the store while this audit reported it clean.

    It gets its own status because documentation cannot excuse it: a documented
    null is a deliberate, conforming state, whereas the placeholder is a third
    persisted state the store may not hold at all and the row needs repairing.
    """
    if row.get("epic") is None:
        return "documented-null" if evidence is not None else "undocumented-null"
    if persisted_projection(row=row):
        return "persisted-projection"
    return None


def audit_null_epics(
    *,
    store_path: str | os.PathLike[str] | None = None,
) -> list[NullEpicAuditRow]:
    """Classify raw rows with no recorded epic, without relying on Track projection.

    ``read_valid_mapping`` intentionally projects an absent plan epic to the
    unresolved placeholder, so this audit has to read raw rows. A deliberate null
    is documented by a non-empty ``epic_null_audit`` field; a raw null without that
    field remains an unfilled gap; and a placeholder that reached the store despite
    the write-side prohibition is surfaced under its own status.
    """
    audited: list[NullEpicAuditRow] = []
    for record in read_row_records(store_path=store_path):
        row = record.row
        topic = row.get("topic")
        repo = row.get("repo")
        if not isinstance(topic, str) or not isinstance(repo, str):
            continue
        evidence = _audit_evidence(row=row)
        status = _audit_status(row=row, evidence=evidence)
        if status is None:
            continue
        audited.append(
            NullEpicAuditRow(
                repo=repo,
                topic=topic,
                lineno=record.lineno,
                status=status,
                evidence=evidence,
            )
        )
    return audited
