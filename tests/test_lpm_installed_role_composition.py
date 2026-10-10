"""Installed role ports retain authoritative target evidence across an interrupted commit."""

from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
from typing import Protocol

import pytest

from overseer._lpm_config import default_config
from overseer._lpm_localstate import read_local_record
from overseer._lpm_paths import local_record_path
from overseer._lpm_results import store_unavailable
from overseer._lpm_target import COMMITTED, IN_PROGRESS, UNCOMMITTED
from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_RUN = "run-installed-role"
_REFERENCE = "10000000-0000-4000-8000-000000000001"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_PREPARED = "2026-10-10T18:00:00Z"
_COMMITTED = "2026-10-10T18:00:01Z"
_EXPIRES = "2026-10-10T19:00:00Z"
_SECRET = b"credential-confined-to-the-role-child"


class _StatusRecord(Protocol):
    status: str


def _assert_carried_modules(*, root: Path) -> None:
    for name in (
        "_lpm_runtime_backend.py",
        "_lpm_role_service.py",
        "_lpm_target_evidence.py",
    ):
        assert (root / "overseer" / name).is_file(), f"overseer/{name} must exist"
        assert (root / ".claude-plugin" / "overseer" / name).read_bytes() == (
            root / "overseer" / name
        ).read_bytes()


def _interrupted_commit(*, binding: object, monkeypatch: pytest.MonkeyPatch):
    evidence = importlib.import_module("_lpm_target_evidence")
    samples = iter((_PREPARED, _COMMITTED))
    real_write = evidence.write_target_evidence
    interrupted = [True]

    def fail_committed_once(*, path: Path, record: _StatusRecord, owner_uid: int):
        if record.status == COMMITTED and interrupted.pop():
            return Failure(store_unavailable(message="post-replacement evidence interruption"))
        return real_write(path=path, record=record, owner_uid=owner_uid)

    monkeypatch.setattr(evidence, "write_target_evidence", fail_committed_once)
    first = evidence.commit_with_evidence(
        binding=binding,
        value=_SECRET,
        lease_expires_at=_EXPIRES,
        sample_time=lambda: next(samples),
    )
    return evidence, real_write, first


def _assert_committed_record(*, path: Path) -> None:
    committed = read_local_record(path=path, owner_uid=os.getuid()).unwrap()
    assert isinstance(committed, dict)
    assert committed == {
        "version": 1,
        "status": "committed",
        "target_ref": _REFERENCE,
        "consumer_run_id": _RUN,
        "value_generation": _GENERATION,
        "target_sha256": hashlib.sha256(_SECRET).hexdigest(),
        "prepared_at": _PREPARED,
        "committed_at": _COMMITTED,
    }


def _assert_expired_write_is_unchanged(*, evidence: object, binding: object) -> None:
    destination = Path(binding.destination)
    previous = destination.read_bytes()
    expired = evidence.commit_with_evidence(
        binding=binding,
        value=b"must-not-replace",
        lease_expires_at=_PREPARED,
        sample_time=lambda: _PREPARED,
    )
    assert expired.status == UNCOMMITTED
    assert destination.read_bytes() == previous


def _assert_runtime_ports(
    *, runtime_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runtime_module, "account_database_home", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(
        runtime_module,
        "load_manager_config",
        lambda **_kwargs: Success(default_config()),
    )
    runtime = runtime_module.runtime_for_host().unwrap()
    assert runtime.store is runtime.provision_target
    assert runtime.target_status is not None
    assert type(runtime.store).__name__ == "RolePorts"


def test_installed_runtime_recovers_the_authoritative_target_commit(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).parents[1]
    _assert_carried_modules(root=root)

    evidence = importlib.import_module("_lpm_target_evidence")
    runtime_module = importlib.import_module("_lpm_runtime")
    binding = evidence.TargetEvidenceBinding(
        state_dir=tmp_path / "state",
        destination=str(tmp_path / "target" / "credential"),
        owner_uid=os.getuid(),
        target_ref=_REFERENCE,
        consumer_run_id=_RUN,
        value_generation=_GENERATION,
    )
    evidence, real_write, first = _interrupted_commit(binding=binding, monkeypatch=monkeypatch)

    assert first.status == IN_PROGRESS
    assert Path(binding.destination).read_bytes() == _SECRET
    path = local_record_path(
        state_dir=binding.state_dir,
        family="target-commit",
        identity=(_REFERENCE,),
    ).unwrap()
    armed = read_local_record(path=path, owner_uid=os.getuid()).unwrap()
    assert isinstance(armed, dict)
    assert armed["status"] == "armed"
    assert armed["committed_at"] == _COMMITTED

    monkeypatch.setattr(evidence, "write_target_evidence", real_write)
    recovered = evidence.target_status_with_evidence(binding=binding)

    assert isinstance(recovered, Success)
    assert recovered.unwrap().status == COMMITTED
    assert recovered.unwrap().committed_at == _COMMITTED
    _assert_committed_record(path=path)

    replay = evidence.target_status_with_evidence(binding=binding)
    assert isinstance(replay, Success)
    assert replay.unwrap() == recovered.unwrap()
    _assert_expired_write_is_unchanged(evidence=evidence, binding=binding)
    _assert_runtime_ports(runtime_module=runtime_module, tmp_path=tmp_path, monkeypatch=monkeypatch)
