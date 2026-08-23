"""Lifecycle helpers for wait-target-missing attention."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from pathlib import Path

import _supervisor_wait_target_sources
import wait_premises

__all__: list[str] = [
    "clear_premise_with_evidence",
    "evidence_path",
    "expired_and_no_longer_waiting",
    "relay_allowed",
    "relay_text",
    "remove_premise",
]

EvidenceWriter = Callable[..., Path | None]


def evidence_path(*, repo: Path, topic: str, key: str) -> Path:
    digest = sha256(key.encode("utf-8")).hexdigest()[:16]
    return repo / "tmp" / "overseer" / topic / f"wait-target-missing-{digest}.json"


def recheck_by_epoch(*, record: dict[str, object]) -> float:
    recheck_by = _supervisor_wait_target_sources.string_field(record=record, key="recheck_by")
    if recheck_by is None:
        return 0.0
    return datetime.fromisoformat(recheck_by.replace("Z", "+00:00")).timestamp()


def expired_and_no_longer_waiting(
    *, status: str, observed_at: float, record: dict[str, object]
) -> bool:
    return status != "blocked:human" and observed_at >= recheck_by_epoch(record=record)


def remove_premise(*, repo: Path, topic: str, record: dict[str, object]) -> None:
    kind = _supervisor_wait_target_sources.string_field(record=record, key="kind")
    target_id = _supervisor_wait_target_sources.string_field(record=record, key="target_id")
    if kind is not None and target_id is not None:
        _ = wait_premises.remove_wait_premise(
            repo=repo, topic=topic, kind=kind, target_id=target_id
        )


def clear_premise_with_evidence(
    *,
    repo: Path,
    topic: str,
    record: dict[str, object],
    key: str,
    status: str,
    write_evidence: EvidenceWriter,
) -> None:
    note = f"wait premise lifecycle cleared: {status}"
    # The daemon removes its own scratch premise only after writing this evidence
    # record, so the premise's existence is still auditable after cleanup.
    if write_evidence(repo=repo, topic=topic, key=key, record=record, status=status, note=note):
        remove_premise(repo=repo, topic=topic, record=record)


def relay_allowed(*, idle: bool, busy: bool, gate: bool) -> bool:
    # Use the runtime-agnostic structural prompt state. A gate includes pickers, and
    # relaying there would choose the session's next action; this relay delivers FACTS
    # only. The relay text must also stay clear of Codex busy-marker substrings because
    # the verified submit path confirms Codex delivery by reading busy over the capture.
    return idle and not busy and not gate


def relay_text(
    *, record: dict[str, object], note: str, evidence_path: Path, evidence_source: str | None
) -> str:
    kind = _supervisor_wait_target_sources.string_field(record=record, key="kind") or "unknown"
    target_id = (
        _supervisor_wait_target_sources.string_field(record=record, key="target_id") or "unknown"
    )
    source = evidence_source or "unknown"
    return (
        "wait-target-missing evidence relay\n"
        f"premise: {kind} {target_id}\n"
        f"re-query: {source}\n"
        f"evidence record: {evidence_path}\n"
        f"result: {note}\n\n"
        "This delivers facts only. It does not choose your next action, does not "
        "authorize a restart, and does not change the ready-file interlock."
    )
