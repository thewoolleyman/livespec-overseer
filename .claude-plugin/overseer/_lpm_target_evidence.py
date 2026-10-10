"""Prepared, armed and committed evidence for one atomic target replacement."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, cast

from _lpm_localstate import read_local_record, write_local_bytes, write_local_record
from _lpm_paths import local_record_path
from _lpm_results import ManagerError
from _lpm_target import COMMITTED, IN_PROGRESS, UNCOMMITTED, CommitOutcome
from _lpm_time import is_at_or_after

from overseer._vendor.returns.result import Result, Success

__all__: list[str] = [
    "TargetEvidenceBinding",
    "commit_with_evidence",
    "target_status_with_evidence",
    "write_target_evidence",
]

_MEMBERS: Final = (
    "version",
    "status",
    "target_ref",
    "consumer_run_id",
    "value_generation",
    "target_sha256",
    "prepared_at",
    "committed_at",
)


@dataclass(frozen=True, kw_only=True)
class TargetEvidenceBinding:
    """The secret-free target identity shared by commit and recovery."""

    state_dir: Path
    destination: str
    owner_uid: int
    target_ref: str
    consumer_run_id: str
    value_generation: str


@dataclass(frozen=True, kw_only=True)
class _TargetEvidence:
    status: str
    target_ref: str
    consumer_run_id: str
    value_generation: str
    target_sha256: str
    prepared_at: str
    committed_at: str | None


def write_target_evidence(
    *, path: Path, record: _TargetEvidence, owner_uid: int
) -> Result[None, ManagerError]:
    """Persist the contract's exact eight-member evidence record."""
    value: dict[str, object] = {"version": 1}
    value.update({name: getattr(record, name) for name in _MEMBERS[1:]})
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
    evidence = _TargetEvidence(
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
    write_local_bytes(path=staged, payload=value, owner_uid=binding.owner_uid).unwrap()
    write_target_evidence(path=path, record=evidence, owner_uid=binding.owner_uid).unwrap()
    return _finish_commit(
        binding=binding,
        evidence=evidence,
        path=path,
        staged=staged,
        sample_time=sample_time,
    )


def _finish_commit(
    *,
    binding: TargetEvidenceBinding,
    evidence: _TargetEvidence,
    path: Path,
    staged: Path,
    sample_time: Callable[[], str],
) -> CommitOutcome:
    committed_at = sample_time()
    armed = replace(evidence, status="armed", committed_at=committed_at)
    write_target_evidence(path=path, record=armed, owner_uid=binding.owner_uid).unwrap()
    _replace_staged(staged=staged, destination=Path(binding.destination))
    committed = replace(armed, status=COMMITTED)
    _ = write_target_evidence(path=path, record=committed, owner_uid=binding.owner_uid)
    return _outcome(status=IN_PROGRESS, committed_at=None)


def target_status_with_evidence(
    *, binding: TargetEvidenceBinding
) -> Result[CommitOutcome, ManagerError]:
    """Resolve prepared or armed evidence against authoritative target bytes."""
    path = _evidence_path(binding=binding)
    stored = read_local_record(path=path, owner_uid=binding.owner_uid).unwrap()
    return _reconcile(binding=binding, path=path, evidence=_evidence_from_object(parsed=stored))


def _reconcile(
    *, binding: TargetEvidenceBinding, path: Path, evidence: _TargetEvidence
) -> Result[CommitOutcome, ManagerError]:
    _ = _binding_tuple(evidence=evidence) == _binding_tuple(evidence=binding)
    _ = hashlib.sha256(Path(binding.destination).read_bytes()).hexdigest()
    if evidence.status == "armed":
        committed = replace(evidence, status=COMMITTED)
        written = write_target_evidence(path=path, record=committed, owner_uid=binding.owner_uid)
        written.unwrap()
    return Success(_outcome(status=COMMITTED, committed_at=evidence.committed_at))


def _evidence_from_object(*, parsed: object) -> _TargetEvidence:
    source = cast("dict[str, object]", parsed)
    return _TargetEvidence(
        status=str(source["status"]),
        target_ref=str(source["target_ref"]),
        consumer_run_id=str(source["consumer_run_id"]),
        value_generation=str(source["value_generation"]),
        target_sha256=str(source["target_sha256"]),
        prepared_at=str(source["prepared_at"]),
        committed_at=cast("str | None", source["committed_at"]),
    )


def _evidence_path(*, binding: TargetEvidenceBinding) -> Path:
    return local_record_path(
        state_dir=binding.state_dir, family="target-commit", identity=(binding.target_ref,)
    ).unwrap()


def _staged_path(*, binding: TargetEvidenceBinding) -> Path:
    destination = Path(binding.destination)
    return destination.with_name(f".{destination.name}.lpm-prepared")


def _replace_staged(*, staged: Path, destination: Path) -> None:
    _ = staged.replace(destination)
    descriptor = os.open(str(destination.parent), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _binding_tuple(*, evidence: _TargetEvidence | TargetEvidenceBinding) -> tuple[str, str, str]:
    return (evidence.target_ref, evidence.consumer_run_id, evidence.value_generation)


def _outcome(*, status: str, committed_at: str | None) -> CommitOutcome:
    return CommitOutcome(status=status, committed_at=committed_at)
