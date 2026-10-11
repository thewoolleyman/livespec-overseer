"""Prepared, armed and committed evidence for one atomic target replacement."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from _lpm_localstate import (
    read_local_record,
    remove_local_record,
    write_local_bytes,
    write_local_record,
)
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, store_unavailable
from _lpm_target import COMMITTED, IN_PROGRESS, UNCOMMITTED, CommitOutcome
from _lpm_target_evidence_io import replace_staged_target, target_matches_evidence
from _lpm_target_evidence_record import (
    TARGET_EVIDENCE_MEMBERS,
    TargetEvidence,
    target_evidence_from_object,
)
from _lpm_time import is_at_or_after

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "TargetEvidence",
    "TargetEvidenceBinding",
    "commit_with_evidence",
    "target_evidence_from_object",
    "target_status_with_evidence",
    "write_target_evidence",
]

_NOT_MATCHED = False


@dataclass(frozen=True, kw_only=True)
class TargetEvidenceBinding:
    """The secret-free target identity shared by commit and recovery."""

    state_dir: Path
    destination: str
    owner_uid: int
    target_ref: str
    consumer_run_id: str
    value_generation: str


def write_target_evidence(
    *, path: Path, record: TargetEvidence, owner_uid: int
) -> Result[None, ManagerError]:
    """Persist the contract's exact eight-member evidence record."""
    value: dict[str, object] = {"version": 1}
    value.update({name: getattr(record, name) for name in TARGET_EVIDENCE_MEMBERS[1:]})
    return write_local_record(path=path, value=value, owner_uid=owner_uid)


def commit_with_evidence(
    *,
    binding: TargetEvidenceBinding,
    value: bytes,
    lease_expires_at: str,
    sample_time: Callable[[], str],
) -> CommitOutcome:
    """Stage, arm, atomically replace, then durably acknowledge one target write."""
    prepared_at = sample_time()
    if is_at_or_after(moment=prepared_at, limit=lease_expires_at) is not False:
        return _outcome(status=UNCOMMITTED, committed_at=None)
    evidence = TargetEvidence(
        status="prepared",
        target_ref=binding.target_ref,
        consumer_run_id=binding.consumer_run_id,
        value_generation=binding.value_generation,
        target_sha256=hashlib.sha256(value).hexdigest(),
        prepared_at=prepared_at,
        committed_at=None,
    )
    path = _evidence_path(binding=binding)
    staged = _staged_path(binding=binding)
    staged_write = write_local_bytes(path=staged, payload=value, owner_uid=binding.owner_uid)
    if isinstance(staged_write, Failure):
        return _outcome(status=UNCOMMITTED, committed_at=None)
    prepared = write_target_evidence(path=path, record=evidence, owner_uid=binding.owner_uid)
    if isinstance(prepared, Failure):
        cleaned = _discard_attempt(binding=binding, path=path, staged=staged)
        return _outcome(
            status=UNCOMMITTED if isinstance(cleaned, Success) else IN_PROGRESS,
            committed_at=None,
        )
    return _finish_commit(
        binding=binding,
        evidence=evidence,
        path=path,
        staged=staged,
        lease_expires_at=lease_expires_at,
        sample_time=sample_time,
    )


def _finish_commit(
    *,
    binding: TargetEvidenceBinding,
    evidence: TargetEvidence,
    path: Path,
    staged: Path,
    lease_expires_at: str,
    sample_time: Callable[[], str],
) -> CommitOutcome:
    committed_at = sample_time()
    if is_at_or_after(moment=committed_at, limit=lease_expires_at) is not False:
        cleaned = _discard_attempt(binding=binding, path=path, staged=staged)
        return _outcome(
            status=UNCOMMITTED if isinstance(cleaned, Success) else IN_PROGRESS,
            committed_at=None,
        )
    armed = replace(evidence, status="armed", committed_at=committed_at)
    armed_write = write_target_evidence(path=path, record=armed, owner_uid=binding.owner_uid)
    if isinstance(armed_write, Failure):
        cleaned = _discard_attempt(binding=binding, path=path, staged=staged)
        return _outcome(
            status=UNCOMMITTED if isinstance(cleaned, Success) else IN_PROGRESS,
            committed_at=None,
        )
    replaced = replace_staged_target(staged=staged, destination=Path(binding.destination))
    if isinstance(replaced, Failure):
        return _outcome(status=IN_PROGRESS, committed_at=None)
    committed = replace(armed, status=COMMITTED)
    persisted = write_target_evidence(path=path, record=committed, owner_uid=binding.owner_uid)
    return (
        _outcome(status=IN_PROGRESS, committed_at=None)
        if isinstance(persisted, Failure)
        else _outcome(status=COMMITTED, committed_at=committed_at)
    )


def target_status_with_evidence(
    *, binding: TargetEvidenceBinding
) -> Result[CommitOutcome, ManagerError]:
    """Resolve prepared or armed evidence against authoritative target bytes."""
    path = _evidence_path(binding=binding)
    reading = read_local_record(path=path, owner_uid=binding.owner_uid)
    if isinstance(reading, Failure):
        return reading
    stored = reading.unwrap()
    if stored is None:
        return Success(_outcome(status=UNCOMMITTED, committed_at=None))
    parsed = target_evidence_from_object(parsed=stored)
    if isinstance(parsed, Failure):
        return Failure(parsed.failure())
    return _reconcile(binding=binding, path=path, evidence=parsed.unwrap())


def _reconcile(
    *, binding: TargetEvidenceBinding, path: Path, evidence: TargetEvidence
) -> Result[CommitOutcome, ManagerError]:
    if _binding_tuple(evidence=evidence) != _binding_tuple(evidence=binding):
        return Failure(store_unavailable(message="target evidence names another binding"))
    if evidence.status == "prepared":
        return _discard_prepared(binding=binding, path=path)
    if evidence.status == COMMITTED:
        return Success(_outcome(status=COMMITTED, committed_at=evidence.committed_at))
    return _reconcile_armed(binding=binding, path=path, evidence=evidence)


def _discard_prepared(
    *, binding: TargetEvidenceBinding, path: Path
) -> Result[CommitOutcome, ManagerError]:
    cleaned = _discard_attempt(binding=binding, path=path, staged=_staged_path(binding=binding))
    if isinstance(cleaned, Failure):
        return cleaned
    return Success(_outcome(status=UNCOMMITTED, committed_at=None))


def _reconcile_armed(
    *, binding: TargetEvidenceBinding, path: Path, evidence: TargetEvidence
) -> Result[CommitOutcome, ManagerError]:
    matching = target_matches_evidence(
        destination=Path(binding.destination),
        owner_uid=binding.owner_uid,
        target_sha256=evidence.target_sha256,
    )
    if isinstance(matching, Failure):
        return matching
    if not matching.unwrap():
        removed = remove_local_record(path=path, owner_uid=binding.owner_uid)
        if isinstance(removed, Failure):
            return removed
        return Success(_outcome(status=UNCOMMITTED, committed_at=None))
    committed = replace(evidence, status=COMMITTED)
    persisted = write_target_evidence(path=path, record=committed, owner_uid=binding.owner_uid)
    if isinstance(persisted, Failure):
        return persisted
    return Success(_outcome(status=COMMITTED, committed_at=evidence.committed_at))


def _evidence_path(*, binding: TargetEvidenceBinding) -> Path:
    return local_record_path(
        state_dir=binding.state_dir, family="target-commit", identity=(binding.target_ref,)
    ).unwrap()


def _staged_path(*, binding: TargetEvidenceBinding) -> Path:
    destination = Path(binding.destination)
    return destination.with_name(f".{destination.name}.lpm-prepared")


def _discard_attempt(
    *, binding: TargetEvidenceBinding, path: Path, staged: Path
) -> Result[None, ManagerError]:
    try:
        staged.unlink(missing_ok=True)
    except OSError as failure:
        return Failure(
            store_unavailable(
                message=f"staged target was not removed: {failure.__class__.__name__}"
            )
        )
    return remove_local_record(path=path, owner_uid=binding.owner_uid)


def _binding_tuple(*, evidence: TargetEvidence | TargetEvidenceBinding) -> tuple[str, str, str]:
    return (evidence.target_ref, evidence.consumer_run_id, evidence.value_generation)


def _outcome(*, status: str, committed_at: str | None) -> CommitOutcome:
    return CommitOutcome(status=status, committed_at=committed_at)
