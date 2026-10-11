"""Regression proofs for the accepted concrete-runtime review findings."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import cast

import pytest

import overseer._lpm_effects_shared as shared_effects
import overseer._lpm_runtime_provision_recovery as provision_recovery
import overseer._lpm_target_evidence as target_evidence
from overseer._lpm_assignment import Assignment, assignment_object, assignment_path
from overseer._lpm_attention import attention_items
from overseer._lpm_canonical import canonical_json_text
from overseer._lpm_config import ManagerConfig, default_config
from overseer._lpm_engine_context import (
    EffectContext,
    EffectInputs,
    OperationEngine,
    SelectedCredential,
)
from overseer._lpm_leases import AccountLease, lease_object
from overseer._lpm_localstate import write_local_record
from overseer._lpm_locks import HeldLock, release_lock, take_lock
from overseer._lpm_operation import OperationRecord
from overseer._lpm_operation_identity import effect_positions
from overseer._lpm_paths import local_record_path
from overseer._lpm_provision_request import ProvisionRequest
from overseer._lpm_results import ManagerError, store_unavailable
from overseer._lpm_role_runner import RoleCompletion
from overseer._lpm_runtime_backend import RolePorts
from overseer._lpm_runtime_roles import FinalProvisioningRequest, TargetStatusRequest
from overseer._lpm_selection_state import SelectionState
from overseer._lpm_store import ConditionalSet, InMemorySecretStore, SecretStore
from overseer._lpm_target import COMMITTED, IN_PROGRESS, UNCOMMITTED, CommitOutcome, TargetLock
from overseer._lpm_target_evidence import (
    TargetEvidence,
    TargetEvidenceBinding,
    commit_with_evidence,
    target_evidence_from_object,
    target_status_with_evidence,
)
from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = []

_NOW = "2026-10-10T20:00:00Z"
_COMMITTED_AT = "2026-10-10T20:00:01Z"
_EXPIRES = "2026-10-10T21:00:00Z"
_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"
_OPERATION = "10000000-0000-4000-8000-000000000001"
_SECRET = b"review-secret-never-rendered"


def _store_failure(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(store_unavailable(message="injected unavailable"))


def _binding(*, tmp_path: Path, suffix: str) -> TargetEvidenceBinding:
    return TargetEvidenceBinding(
        state_dir=tmp_path / "state",
        destination=str(tmp_path / "targets" / suffix / "credential"),
        owner_uid=os.getuid(),
        target_ref=f"target-{suffix}",
        consumer_run_id=f"run-{suffix}",
        value_generation=_GENERATION,
    )


def _evidence_path(*, binding: TargetEvidenceBinding) -> Path:
    return local_record_path(
        state_dir=binding.state_dir,
        family="target-commit",
        identity=(binding.target_ref,),
    ).unwrap()


def _evidence_object(
    *, binding: TargetEvidenceBinding, status: str, committed_at: str | None
) -> dict[str, object]:
    return {
        "version": 1,
        "status": status,
        "target_ref": binding.target_ref,
        "consumer_run_id": binding.consumer_run_id,
        "value_generation": binding.value_generation,
        "target_sha256": hashlib.sha256(_SECRET).hexdigest(),
        "prepared_at": _NOW,
        "committed_at": committed_at,
    }


def _seed_evidence(
    *, binding: TargetEvidenceBinding, status: str, committed_at: str | None
) -> None:
    write_local_record(
        path=_evidence_path(binding=binding),
        value=_evidence_object(binding=binding, status=status, committed_at=committed_at),
        owner_uid=binding.owner_uid,
    ).unwrap()


def test_target_evidence_write_failures_return_uncommitted_and_clean_attempt_state(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged_failure = _binding(tmp_path=tmp_path, suffix="staged-failure")
    monkeypatch.setattr(
        target_evidence,
        "write_local_bytes",
        _store_failure,
    )
    staged = commit_with_evidence(
        binding=staged_failure,
        value=_SECRET,
        lease_expires_at=_EXPIRES,
        sample_time=iter((_NOW, _COMMITTED_AT)).__next__,
    )
    assert staged.status == UNCOMMITTED
    assert not Path(staged_failure.destination).exists()
    assert not _evidence_path(binding=staged_failure).exists()

    monkeypatch.undo()
    armed_failure = _binding(tmp_path=tmp_path, suffix="armed-failure")
    real_write = target_evidence.write_target_evidence
    writes = 0

    def fail_armed(
        *, path: Path, record: TargetEvidence, owner_uid: int
    ) -> Result[None, ManagerError]:
        nonlocal writes
        writes += 1
        if writes == 2:
            return Failure(store_unavailable(message="arming unavailable"))
        return real_write(path=path, record=record, owner_uid=owner_uid)

    monkeypatch.setattr(target_evidence, "write_target_evidence", fail_armed)
    armed = commit_with_evidence(
        binding=armed_failure,
        value=_SECRET,
        lease_expires_at=_EXPIRES,
        sample_time=iter((_NOW, _COMMITTED_AT)).__next__,
    )
    staged_path = Path(armed_failure.destination).with_name(".credential.lpm-prepared")
    assert armed.status == UNCOMMITTED
    assert not staged_path.exists()
    assert not _evidence_path(binding=armed_failure).exists()


def test_committed_evidence_is_authoritative_and_armed_evidence_requires_a_safe_target(
    *, tmp_path: Path
) -> None:
    committed = _binding(tmp_path=tmp_path, suffix="committed")
    _seed_evidence(binding=committed, status=COMMITTED, committed_at=_COMMITTED_AT)
    settled = target_status_with_evidence(binding=committed).unwrap()
    assert settled.status == COMMITTED
    assert settled.committed_at == _COMMITTED_AT
    assert _evidence_path(binding=committed).exists()

    for suffix, mode in (("absent", None), ("broad", 0o644), ("symlink", 0o600)):
        binding = _binding(tmp_path=tmp_path, suffix=suffix)
        destination = Path(binding.destination)
        destination.parent.mkdir(parents=True, mode=0o700)
        if mode is not None:
            if suffix == "symlink":
                target = destination.with_name("real-credential")
                _ = target.write_bytes(_SECRET)
                target.chmod(mode)
                _ = destination.symlink_to(target)
            else:
                _ = destination.write_bytes(_SECRET)
                destination.chmod(mode)
        _seed_evidence(binding=binding, status="armed", committed_at=_COMMITTED_AT)
        outcome = target_status_with_evidence(binding=binding).unwrap()
        assert outcome.status == UNCOMMITTED
        assert not _evidence_path(binding=binding).exists()


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("version", True),
        ("status", "unknown"),
        ("target_ref", 7),
        ("consumer_run_id", ""),
        ("value_generation", "not-a-uuid"),
        ("target_sha256", "ABC"),
        ("prepared_at", "not-a-time"),
        ("committed_at", None),
    ],
)
def test_target_evidence_decoder_refuses_malformed_members(member: str, value: object) -> None:
    binding = TargetEvidenceBinding(
        state_dir=Path("/unused"),
        destination="/unused/credential",
        owner_uid=os.getuid(),
        target_ref="target-valid",
        consumer_run_id="run-valid",
        value_generation=_GENERATION,
    )
    source = _evidence_object(binding=binding, status="armed", committed_at=_COMMITTED_AT)
    source[member] = value
    assert isinstance(target_evidence_from_object(parsed=source), Failure)


def _attention_artifact() -> dict[str, object]:
    return {
        "version": 1,
        "type": "browser-verification-wall",
        "record_id": _RECORD,
        "operation_id": _OPERATION,
        "worker_pid": 321,
        "worker_start_ticks": 654,
        "provider": "anthropic",
        "account_id": "account-a",
        "reason": "captcha",
        "status": "pending",
        "raised_at": _NOW,
        "deadline": _EXPIRES,
    }


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("version", False),
        ("type", "other"),
        ("record_id", "not-a-uuid"),
        ("operation_id", "not-a-uuid"),
        ("worker_pid", 0),
        ("worker_start_ticks", -1),
        ("provider", ""),
        ("reason", "password"),
        ("status", "unknown"),
        ("raised_at", "not-a-time"),
        ("deadline", _NOW),
    ],
)
def test_attention_returns_a_typed_failure_for_malformed_artifacts(
    *, tmp_path: Path, member: str, value: object
) -> None:
    state_dir = tmp_path / member
    source = _attention_artifact()
    source[member] = value
    write_local_record(
        path=state_dir / "attention" / f"{_RECORD}.json",
        value=source,
        owner_uid=os.getuid(),
    ).unwrap()
    result = attention_items(state_dir=state_dir, owner_uid=os.getuid())
    assert isinstance(result, Failure)
    assert result.failure().error_type == "store-unavailable"


@dataclass(frozen=True, kw_only=True)
class _RecoveryHost:
    state_dir: Path
    owner_uid: int
    config: ManagerConfig
    store: SecretStore
    op_executable: str | None
    capture_time: Callable[[], str]
    new_operation_id: Callable[[], str]
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]
    provision_target: _UnusedTarget
    target_status: None


@dataclass(frozen=True, kw_only=True)
class _UnusedTarget:
    def __call__(
        self,
        *,
        request: FinalProvisioningRequest,
        destination: str,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        _ = (request, destination, lock)
        return _store_failure()


def _credential_record() -> dict[str, object]:
    return {
        "version": 1,
        "record_id": _RECORD,
        "provider": "anthropic",
        "account_id": "account-a",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "status": "valid",
        "acquired_at": _NOW,
        "expires_at": None,
        "last_validated": _NOW,
        "value_generation": _GENERATION,
        "value_ref": f"op://values/{_GENERATION}/credential",
        "previous_value_ref": None,
    }


def test_provision_recovery_reconstructs_the_committed_lease_selection(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = InMemorySecretStore()
    seeded = store.credential_conditional_set(
        request=ConditionalSet(
            record_id=_RECORD,
            effect_id="c" * 64,
            expected_record=None,
            desired_record=canonical_json_text(value=_credential_record()).unwrap(),
        )
    )
    assert seeded["status"] == COMMITTED
    host = _RecoveryHost(
        state_dir=tmp_path / "state",
        owner_uid=os.getuid(),
        config=default_config(),
        store=store,
        op_executable=None,
        capture_time=lambda: _NOW,
        new_operation_id=lambda: _OPERATION,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
        provision_target=_UnusedTarget(),
        target_status=None,
    )
    request = ProvisionRequest(
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        consumer_run_id="run-recovery",
        target_ref="target-recovery",
        strategy="consume-first",
        lease_seconds=3600,
    )
    operation = OperationRecord(
        operation_id=_OPERATION,
        command="provision",
        phase="start",
        idempotency_key="a" * 64,
        accepted_at=_NOW,
        normalized_input={
            "version": 1,
            "provider": request.provider,
            "kind": request.kind,
            "purpose": request.purpose,
            "consumer_run_id": request.consumer_run_id,
            "target_ref": request.target_ref,
            "strategy": request.strategy,
            "lease_seconds": request.lease_seconds,
        },
        terminal_result=None,
        ordered_effects=("lease-create", "prepared-assignment-create", "target-write"),
        completed_step=0,
    )
    lease = AccountLease(
        provider=request.provider,
        account_id="account-a",
        record_id=_RECORD,
        consumer_run_id=request.consumer_run_id,
        lease_started_at=_NOW,
        lease_expires_at=_EXPIRES,
    )
    lease_path = local_record_path(
        state_dir=host.state_dir,
        family="lease",
        identity=(request.provider, lease.account_id),
    ).unwrap()
    write_local_record(
        path=lease_path,
        value=lease_object(lease=lease),
        owner_uid=os.getuid(),
    ).unwrap()
    selected: list[str] = []

    def capture_inputs(**kwargs: object) -> Success[EffectInputs]:
        selected.append(cast("SelectedCredential", kwargs["selected"]).record_id)
        return Success(EffectInputs())

    monkeypatch.setattr(provision_recovery, "selected_for_request", _store_failure)
    monkeypatch.setattr(provision_recovery, "provision_effect_inputs", capture_inputs)

    def successful_drive(**_kwargs: object) -> Success[dict[str, object]]:
        return Success({"operation": "provision", "receipt": {}})

    monkeypatch.setattr(
        provision_recovery,
        "drive_provision",
        successful_drive,
    )
    result = provision_recovery.resume_provision(
        host=host,
        request=request,
        operation=operation,
        assignment=None,
    )
    assert isinstance(result, Success)
    assert selected == [_RECORD]


def _committed_assignment() -> Assignment:
    request: dict[str, object] = {
        "version": 1,
        "provider": "anthropic",
        "kind": "claude-code-oauth",
        "purpose": "factory",
        "consumer_run_id": "run-lock",
        "target_ref": "target-lock",
        "strategy": "consume-first",
        "lease_seconds": 3600,
    }
    return Assignment(
        status="committed",
        request=request,
        target_ref="target-lock",
        account_id="account-a",
        value_generation=_GENERATION,
        value_ref=f"op://values/{_GENERATION}/credential",
        record_id=_RECORD,
        receipt={
            "record_id": _RECORD,
            "account_id": "account-a",
            "purpose": "factory",
            "validated_at": _NOW,
            "lease_expires_at": _EXPIRES,
        },
        lease_started_at=_NOW,
        lease_expires_at=_EXPIRES,
        target_committed_at=_COMMITTED_AT,
        actual_lease_ended_at=None,
        report_markers=(),
        completion=None,
    )


def _selection_update_in_child(
    *, pipe: Connection, context: EffectContext, inherited_lock_descriptor: int
) -> None:
    """Expose the lock/read order from a distinct process without leaking a worker."""
    os.close(inherited_lock_descriptor)
    real_take_lock = shared_effects.take_lock
    real_read_selection_state = shared_effects.read_selection_state

    def observed_take_lock(
        *,
        path: Path,
        owner_uid: int,
        timeout_seconds: float,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> Result[HeldLock, ManagerError]:
        pipe.send("lock-attempt")
        return real_take_lock(
            path=path,
            owner_uid=owner_uid,
            timeout_seconds=timeout_seconds,
            monotonic=monotonic,
            sleep=sleep,
        )

    def observed_read_selection_state(
        *, path: Path, owner_uid: int
    ) -> Result[SelectionState, ManagerError]:
        pipe.send("authoritative-read")
        return real_read_selection_state(path=path, owner_uid=owner_uid)

    shared_effects.take_lock = observed_take_lock
    shared_effects.read_selection_state = observed_read_selection_state
    result = shared_effects.selection_update(context=context)
    pipe.send(("done", None if isinstance(result, Success) else result.failure().message))
    pipe.close()
    os._exit(0)


def _selection_context(*, state_dir: Path, assignment: Assignment) -> EffectContext:
    operation = OperationRecord(
        operation_id=_OPERATION,
        command="provision",
        phase="postcommit",
        idempotency_key="d" * 64,
        accepted_at=_NOW,
        normalized_input=dict(assignment.request),
        terminal_result=None,
        ordered_effects=("selection-update",),
        completed_step=-1,
    )
    return EffectContext(
        engine=OperationEngine(
            state_dir=state_dir,
            owner_uid=os.getuid(),
            store=InMemorySecretStore(),
        ),
        operation=operation,
        inputs=EffectInputs(),
        position=effect_positions(operation=operation)[0],
    )


def test_selection_update_holds_the_shared_lock_before_its_authoritative_read(
    *, tmp_path: Path
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    assignment = _committed_assignment()
    path = assignment_path(
        state_dir=state_dir,
        consumer_run_id=str(assignment.request["consumer_run_id"]),
    ).unwrap()
    write_local_record(
        path=path,
        value=assignment_object(assignment=assignment),
        owner_uid=os.getuid(),
    ).unwrap()
    context = _selection_context(state_dir=state_dir, assignment=assignment)
    held: HeldLock | None = take_lock(
        path=state_dir / "locks" / "selection-state.lock",
        owner_uid=os.getuid(),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    process_context = multiprocessing.get_context("fork")
    parent_end, child_end = process_context.Pipe(duplex=False)
    child = process_context.Process(
        target=_selection_update_in_child,
        kwargs={
            "pipe": child_end,
            "context": context,
            "inherited_lock_descriptor": held.descriptor,
        },
    )
    child.start()
    try:
        assert parent_end.poll(5.0)
        assert parent_end.recv() == "lock-attempt"
        assert not parent_end.poll(0.2), "the authoritative read escaped the held lock"
        release_lock(held=held)
        held = None
        assert parent_end.poll(5.0)
        assert parent_end.recv() == "authoritative-read"
        assert parent_end.poll(5.0)
        assert parent_end.recv() == ("done", None)
        child.join(timeout=5.0)
        assert child.exitcode == 0
    finally:
        if held is not None:
            release_lock(held=held)
        if child.is_alive():
            child.kill()
            child.join(timeout=5.0)


def test_selection_lock_failure_stays_on_the_typed_result_rail(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operation = OperationRecord(
        operation_id=_OPERATION,
        command="provision",
        phase="postcommit",
        idempotency_key="b" * 64,
        accepted_at=_NOW,
        normalized_input=dict(_committed_assignment().request),
        terminal_result=None,
        ordered_effects=("selection-update",),
        completed_step=-1,
    )
    context = EffectContext(
        engine=OperationEngine(
            state_dir=tmp_path / "state",
            owner_uid=os.getuid(),
            store=InMemorySecretStore(),
        ),
        operation=operation,
        inputs=EffectInputs(),
        position=effect_positions(operation=operation)[0],
    )

    def committed(**_kwargs: object) -> Success[Assignment]:
        return Success(_committed_assignment())

    monkeypatch.setattr(shared_effects, "committed_assignment", committed)
    monkeypatch.setattr(shared_effects, "take_lock", _store_failure)
    result = shared_effects.selection_update(context=context)
    assert isinstance(result, Failure)
    assert result.failure().error_type == "store-unavailable"


@dataclass(frozen=True, kw_only=True)
class _ForbiddenLaunch:
    def __call__(
        self,
        *,
        argv: tuple[str, ...],
        environ: Mapping[str, str],
        request_bytes: bytes,
        timeout_seconds: float,
        inherited_fds: tuple[int, ...],
    ) -> RoleCompletion:
        _ = (argv, environ, request_bytes, timeout_seconds, inherited_fds)
        raise AssertionError("a contended status lock must not launch a role")


def test_target_status_uses_one_nonblocking_lock_attempt(*, tmp_path: Path) -> None:
    lock = TargetLock(
        path=tmp_path / "state" / "locks" / "target.lock",
        timeout_seconds=30.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: (_ for _ in ()).throw(AssertionError("must not wait")),
    )
    from overseer._lpm_locks import release_lock, take_lock

    held = take_lock(
        path=lock.path,
        owner_uid=os.getuid(),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    ports = RolePorts(
        config=default_config(),
        owner_uid=os.getuid(),
        state_dir=tmp_path / "state",
        environ={"PATH": "/usr/bin:/bin"},
        launch=_ForbiddenLaunch(),
        python_executable=sys.executable,
        packaged_companion=str(tmp_path / "_lpm_companion.py"),
    )
    try:
        result = ports.target_status(
            request=TargetStatusRequest(
                target_ref="target-a",
                consumer_run_id="run-a",
                value_generation=_GENERATION,
            ),
            destination=str(tmp_path / "ignored"),
            lock=lock,
        )
    finally:
        release_lock(held=held)
    assert isinstance(result, Success)
    assert result.unwrap().status == IN_PROGRESS
    assert result.unwrap().committed_at is None
