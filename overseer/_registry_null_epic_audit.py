"""Raw mapping-store audit for deliberate ``epic: null`` rows."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from _registry_rows_io import read_row_records

__all__: list[str] = [
    "NullEpicAuditRow",
    "audit_null_epics",
]

NullEpicAuditStatus = Literal["documented-null", "undocumented-null"]
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


def audit_null_epics(
    *,
    store_path: str | os.PathLike[str] | None = None,
) -> list[NullEpicAuditRow]:
    """Classify raw ``epic: null`` rows without relying on Track projection.

    ``read_valid_mapping`` intentionally projects a raw null plan epic to the
    unresolved sentinel, so the durable null audit has to read raw rows. A
    deliberate null is documented by a non-empty ``epic_null_audit`` field; a
    raw null without that field remains an unfilled gap.
    """
    audited: list[NullEpicAuditRow] = []
    for record in read_row_records(store_path=store_path):
        row = record.row
        if row.get("epic") is not None:
            continue
        topic = row.get("topic")
        repo = row.get("repo")
        if not isinstance(topic, str) or not isinstance(repo, str):
            continue
        evidence = _audit_evidence(row=row)
        audited.append(
            NullEpicAuditRow(
                repo=repo,
                topic=topic,
                lineno=record.lineno,
                status="documented-null" if evidence is not None else "undocumented-null",
                evidence=evidence,
            )
        )
    return audited
