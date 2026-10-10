"""Authoritative target evidence distinguishes definitive and ambiguous retries."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from overseer._lpm_localstate import read_local_record, write_local_record
from overseer._lpm_paths import local_record_path
from overseer._lpm_results import store_unavailable
from overseer._lpm_target import COMMITTED, UNCOMMITTED
from overseer._lpm_target_evidence import (
    TargetEvidenceBinding,
    commit_with_evidence,
    target_status_with_evidence,
)
from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_REFERENCE = "20000000-0000-4000-8000-000000000002"
_RUN = "run-evidence-recovery"
_GENERATION = "7ba7b810-9dad-41d1-80b4-00c04fd430c9"
_PREPARED = "2026-10-10T20:00:00Z"
_COMMITTED = "2026-10-10T20:00:01Z"
_EXPIRES = "2026-10-10T21:00:00Z"
_VALUE = b"only-the-target-receives-this-value"


def _binding(*, tmp_path: Path, reference: str = _REFERENCE) -> TargetEvidenceBinding:
    return TargetEvidenceBinding(
        state_dir=tmp_path / "state",
        destination=str(tmp_path / reference / "credential"),
        owner_uid=os.getuid(),
        target_ref=reference,
        consumer_run_id=_RUN,
        value_generation=_GENERATION,
    )


def _path(*, binding: TargetEvidenceBinding) -> Path:
    return local_record_path(
        state_dir=binding.state_dir,
        family="target-commit",
        identity=(binding.target_ref,),
    ).unwrap()


def _record(
    *, binding: TargetEvidenceBinding, status: str, digest: str, committed_at: str | None
) -> dict[str, object]:
    return {
        "version": 1,
        "status": status,
        "target_ref": binding.target_ref,
        "consumer_run_id": binding.consumer_run_id,
        "value_generation": binding.value_generation,
        "target_sha256": digest,
        "prepared_at": _PREPARED,
        "committed_at": committed_at,
    }


def _write_record(*, binding: TargetEvidenceBinding, record: object) -> None:
    write_local_record(
        path=_path(binding=binding), value=record, owner_uid=binding.owner_uid
    ).unwrap()


def _commit(*, binding: TargetEvidenceBinding, times: tuple[str, ...]) -> object:
    samples = iter(times)
    return commit_with_evidence(
        binding=binding,
        value=_VALUE,
        lease_expires_at=_EXPIRES,
        sample_time=lambda: next(samples),
    )


def _assert_prepared_retry(*, tmp_path: Path) -> None:
    binding = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-prepared")
    destination = Path(binding.destination)
    staged = destination.with_name(f".{destination.name}.lpm-prepared")
    staged.parent.mkdir(parents=True, mode=0o700)
    staged.write_bytes(_VALUE)
    staged.chmod(0o600)
    _write_record(
        binding=binding,
        record=_record(
            binding=binding,
            status="prepared",
            digest=hashlib.sha256(_VALUE).hexdigest(),
            committed_at=None,
        ),
    )

    result = target_status_with_evidence(binding=binding).unwrap()

    assert result.status == UNCOMMITTED
    assert not staged.exists()
    assert not _path(binding=binding).exists()


def _assert_armed_retries(*, tmp_path: Path) -> None:
    for suffix, payload, expected in (
        ("matching", _VALUE, COMMITTED),
        ("different", b"prior-target-value", UNCOMMITTED),
    ):
        binding = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-{suffix}")
        destination = Path(binding.destination)
        destination.parent.mkdir(parents=True, mode=0o700)
        destination.write_bytes(payload)
        destination.chmod(0o600)
        _write_record(
            binding=binding,
            record=_record(
                binding=binding,
                status="armed",
                digest=hashlib.sha256(_VALUE).hexdigest(),
                committed_at=_COMMITTED,
            ),
        )

        result = target_status_with_evidence(binding=binding).unwrap()

        assert result.status == expected
        assert _path(binding=binding).exists() is (expected == COMMITTED)


def _assert_invalid_evidence_is_typed(*, tmp_path: Path) -> None:
    malformed = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-malformed")
    _write_record(binding=malformed, record={"version": 1})
    assert target_status_with_evidence(binding=malformed).failure().error_type == (
        "store-unavailable"
    )

    mismatched = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-mismatched")
    _write_record(
        binding=mismatched,
        record={
            **_record(
                binding=mismatched,
                status=COMMITTED,
                digest=hashlib.sha256(_VALUE).hexdigest(),
                committed_at=_COMMITTED,
            ),
            "consumer_run_id": "another-run",
        },
    )
    assert target_status_with_evidence(binding=mismatched).failure().error_type == (
        "store-unavailable"
    )


def _assert_write_failures_are_typed(*, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import overseer._lpm_target_evidence as evidence

    binding = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-write-failure")
    real_write = evidence.write_target_evidence

    def unavailable(*, path: Path, record: object, owner_uid: int):
        _ = (path, record, owner_uid)
        return Failure(store_unavailable(message="fixture evidence outage"))

    monkeypatch.setattr(evidence, "write_target_evidence", unavailable)
    result = _commit(binding=binding, times=(_PREPARED, _COMMITTED))
    assert result.status == UNCOMMITTED
    assert not Path(binding.destination).exists()

    monkeypatch.setattr(evidence, "write_target_evidence", real_write)
    missing = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-absent")
    assert isinstance(target_status_with_evidence(binding=missing), Success)
    assert target_status_with_evidence(binding=missing).unwrap().status == UNCOMMITTED


def test_target_evidence_recovers_only_authoritative_commits(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding = _binding(tmp_path=tmp_path)
    committed = _commit(binding=binding, times=(_PREPARED, _COMMITTED))

    assert committed.status == COMMITTED
    assert committed.committed_at == _COMMITTED
    assert Path(binding.destination).read_bytes() == _VALUE
    assert read_local_record(path=_path(binding=binding), owner_uid=os.getuid()).unwrap() == (
        _record(
            binding=binding,
            status=COMMITTED,
            digest=hashlib.sha256(_VALUE).hexdigest(),
            committed_at=_COMMITTED,
        )
    )

    expired = _binding(tmp_path=tmp_path, reference=f"{_REFERENCE}-expired")
    prior = Path(expired.destination)
    prior.parent.mkdir(parents=True, mode=0o700)
    prior.write_bytes(b"prior")
    prior.chmod(0o600)
    samples = iter((_PREPARED, _EXPIRES))
    refused = commit_with_evidence(
        binding=expired,
        value=_VALUE,
        lease_expires_at=_EXPIRES,
        sample_time=lambda: next(samples),
    )
    assert refused.status == UNCOMMITTED
    assert prior.read_bytes() == b"prior"

    _assert_prepared_retry(tmp_path=tmp_path)
    _assert_armed_retries(tmp_path=tmp_path)
    _assert_invalid_evidence_is_typed(tmp_path=tmp_path)
    _assert_write_failures_are_typed(tmp_path=tmp_path, monkeypatch=monkeypatch)
