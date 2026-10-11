"""Accepted second-round runtime findings stay closed at their concrete boundaries."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from overseer._lpm_commands import ManagerInvocation, run_manager_command
from overseer._lpm_config import ManagerConfig, default_config
from overseer._lpm_engine_context import EffectInputs
from overseer._lpm_localstate import write_local_record
from overseer._lpm_locks import release_lock, take_lock
from overseer._lpm_operation import OperationRecord
from overseer._lpm_provision_request import ProvisionRequest
from overseer._lpm_results import ManagerError, store_unavailable
from overseer._lpm_role_context import RoleContext
from overseer._lpm_role_runner import RoleCompletion
from overseer._lpm_runtime_backend import RolePorts
from overseer._lpm_runtime_base import target_lock_path
from overseer._lpm_runtime_provision_drive import ProvisionDrivePorts, drive_provision_phase
from overseer._lpm_runtime_roles import FinalProvisioningRequest
from overseer._lpm_store import InMemorySecretStore, SecretStore
from overseer._lpm_target import UNCOMMITTED, CommitOutcome, TargetLock
from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = []

_NOW = "2026-10-11T09:00:00Z"
_EXPIRES = "2099-10-11T09:00:00Z"
_REFERENCE = "10000000-0000-4000-8000-000000000001"
_RECORD = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_GENERATION = "6ba7b810-9dad-41d1-80b4-00c04fd430c8"


@dataclass(kw_only=True)
class _RecordingRuntime:
    invocations: list[ManagerInvocation]

    def run(self, *, invocation: ManagerInvocation) -> str:
        self.invocations.append(invocation)
        return invocation.command


@dataclass(frozen=True, kw_only=True)
class _DriveHost:
    state_dir: Path
    owner_uid: int
    config: ManagerConfig
    store: SecretStore
    monotonic: Callable[[], float] = lambda: 0.0
    sleep: Callable[[float], None] = lambda _seconds: None


@dataclass(frozen=True, kw_only=True)
class _Completion:
    stdout: bytes

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
        return RoleCompletion(
            stdout=self.stdout,
            exit_status=0,
            timed_out=False,
            started=True,
        )


@dataclass(frozen=True, kw_only=True)
class _DestinationFixture:
    state_dir: Path
    isolated_root: Path
    destination: Path
    protected: Path


def _request() -> FinalProvisioningRequest:
    return FinalProvisioningRequest(
        target_ref=_REFERENCE,
        consumer_run_id="run-review-two",
        record_id=_RECORD,
        value_generation=_GENERATION,
        value_ref=("op://llm-provider-manager-token-values/" f"{_RECORD}-{_GENERATION}/credential"),
        lease_expires_at=_EXPIRES,
        external_call_timeout_seconds=30,
        op_executable="/usr/bin/op",
    )


def _final_members() -> dict[str, object]:
    return {
        "version": 1,
        "target_ref": _REFERENCE,
        "consumer_run_id": "run-review-two",
        "record_id": _RECORD,
        "value_generation": _GENERATION,
        "value_ref": (
            "op://llm-provider-manager-token-values/" f"{_RECORD}-{_GENERATION}/credential"
        ),
        "lease_expires_at": _EXPIRES,
        "external_call_timeout_seconds": 30,
        "op_executable": "/usr/bin/op",
    }


def _target_lock(*, state_dir: Path) -> TargetLock:
    return TargetLock(
        path=target_lock_path(state_dir=state_dir, target_ref=_REFERENCE),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )


def _prerequisites_ok(
    *, root: Path, search_path: Sequence[Path], executable_name: str
) -> Result[object, ManagerError]:
    from overseer._lpm_prereq import RuntimePrerequisites

    _ = (root, search_path, executable_name)
    return Success(RuntimePrerequisites(machine_id_sha256="a" * 64, op_executable="/usr/bin/op"))


def _destination_fixture(*, tmp_path: Path) -> _DestinationFixture:
    from overseer._lpm_paths import local_record_path

    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    isolated_root = tmp_path / "isolated"
    destination = isolated_root / "credentials" / "credential"
    destination.parent.mkdir(mode=0o700, parents=True)
    isolated_root.chmod(0o700)
    destination.parent.chmod(0o700)
    protected = tmp_path / "account-home" / ".claude" / ".credentials.json"
    protected.parent.mkdir(mode=0o700, parents=True)
    protected.parent.parent.chmod(0o700)
    protected.parent.chmod(0o700)
    protected.write_bytes(b"interactive-credential")
    protected.chmod(0o600)
    issuance_path = local_record_path(
        state_dir=state_dir,
        family="issuance",
        identity=(_REFERENCE,),
    ).unwrap()
    write_local_record(
        path=issuance_path,
        value={
            "version": 1,
            "target_ref": _REFERENCE,
            "consumer_run_id": "run-review-two",
            "adapter": "isolated-run",
            "isolated_root": str(isolated_root),
            "target_path": str(destination),
            "issued_at": _NOW,
            "expires_at": _EXPIRES,
        },
        owner_uid=os.getuid(),
    ).unwrap()
    return _DestinationFixture(
        state_dir=state_dir,
        isolated_root=isolated_root,
        destination=destination,
        protected=protected,
    )


def test_explicit_attention_token_reaches_the_shared_runtime() -> None:
    runtime = _RecordingRuntime(invocations=[])

    assert run_manager_command(arguments=("attention",), runtime=runtime) == "attention"
    assert runtime.invocations == [ManagerInvocation(command="attention", source=None)]


def test_target_roles_reject_malformed_shapes_before_context_or_state_access(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_service = importlib.import_module("_lpm_role_target_service")
    context_reads: list[str] = []

    def observed_context() -> Failure[ManagerError]:
        context_reads.append("read")
        return Failure(store_unavailable(message="context should not be read"))

    monkeypatch.setattr(target_service, "role_context", observed_context)
    final = {
        "version": 1,
        "target_ref": _REFERENCE,
        "consumer_run_id": "run-review-two",
        "record_id": _RECORD,
        "value_generation": _GENERATION,
        "value_ref": "op://llm-provider-manager-token-values/wrong/credential",
        "lease_expires_at": _EXPIRES,
        "external_call_timeout_seconds": 30,
        "op_executable": "/usr/bin/op",
    }
    status = {
        "version": 1,
        "target_ref": _REFERENCE,
        "consumer_run_id": "run-review-two",
        "value_generation": _GENERATION,
        "unexpected": True,
    }

    assert target_service.target_role_result(
        role_name="final-provisioning",
        members=final,
        environ={},
        lock_descriptor=None,
    ) == {"version": 1, "status": "store-unavailable"}
    assert target_service.target_role_result(
        role_name="target-status",
        members=status,
        environ={},
        lock_descriptor=None,
    ) == {"version": 1, "status": "store-unavailable"}
    assert target_service.target_role_result(
        role_name="final-provisioning",
        members={"version": 1},
        environ={},
        lock_descriptor=None,
    ) == {"version": 1, "status": "store-unavailable"}
    assert target_service.target_role_result(
        role_name="unknown-target-role",
        members={},
        environ={},
        lock_descriptor=None,
    ) == {"version": 1, "status": "store-unavailable"}
    assert context_reads == []


def test_target_role_state_failures_remain_closed(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_service = importlib.import_module("_lpm_role_target_service")
    monkeypatch.setattr(
        target_service,
        "role_context",
        lambda: Success(
            RoleContext(
                state_dir=tmp_path / "state",
                owner_uid=os.getuid(),
                machine_id_sha256="a" * 64,
            )
        ),
    )
    status = {
        "version": 1,
        "target_ref": _REFERENCE,
        "consumer_run_id": "run-review-two",
        "value_generation": _GENERATION,
    }
    monkeypatch.setattr(
        target_service,
        "local_record_path",
        lambda **_kwargs: Failure(store_unavailable(message="path unavailable")),
    )
    assert target_service.target_role_result(
        role_name="target-status", members=status, environ={}, lock_descriptor=None
    ) == {"version": 1, "status": "store-unavailable"}
    monkeypatch.setattr(
        target_service,
        "local_record_path",
        lambda **_kwargs: Success(tmp_path / "state" / "issuance.json"),
    )
    monkeypatch.setattr(
        target_service,
        "read_local_record",
        lambda **_kwargs: Failure(store_unavailable(message="record unavailable")),
    )
    assert target_service.target_role_result(
        role_name="target-status", members=status, environ={}, lock_descriptor=None
    ) == {"version": 1, "status": "store-unavailable"}


def test_final_role_refuses_a_mismatched_persisted_binding_before_value_access(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_service = importlib.import_module("_lpm_role_target_service")
    fixture = _destination_fixture(tmp_path=tmp_path)
    monkeypatch.setattr(
        target_service,
        "role_context",
        lambda: Success(
            RoleContext(
                state_dir=fixture.state_dir,
                owner_uid=os.getuid(),
                machine_id_sha256="a" * 64,
            )
        ),
    )
    monkeypatch.setattr(
        target_service,
        "resolve_issuance",
        lambda **_kwargs: Failure(store_unavailable(message="binding mismatch")),
    )

    def observe_binding(
        *,
        entry: object,
        reference: object,
        binding: Callable[[], str | None],
        write: Callable[..., CommitOutcome],
    ) -> dict[str, object]:
        _ = (entry, reference, write)
        assert binding() == "target binding unavailable"
        return {"version": 1, "status": "store-unavailable"}

    monkeypatch.setattr(target_service, "provisioning_result", observe_binding)
    held = take_lock(
        path=target_lock_path(state_dir=fixture.state_dir, target_ref=_REFERENCE),
        owner_uid=os.getuid(),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    try:
        outcome = target_service.target_role_result(
            role_name="final-provisioning",
            members=_final_members(),
            environ={},
            lock_descriptor=held.descriptor,
        )
    finally:
        release_lock(held=held)
    assert outcome == {"version": 1, "status": "store-unavailable"}


def test_final_role_revalidates_destination_immediately_before_target_write(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from overseer._lpm_op_values import commit_status_result

    target_service = importlib.import_module("_lpm_role_target_service")
    registration = importlib.import_module("_lpm_runtime_target_registration")
    fixture = _destination_fixture(tmp_path=tmp_path)
    monkeypatch.setattr(
        target_service,
        "role_context",
        lambda: Success(
            RoleContext(
                state_dir=fixture.state_dir,
                owner_uid=os.getuid(),
                machine_id_sha256="a" * 64,
            )
        ),
    )
    monkeypatch.setattr(
        registration,
        "account_database_home",
        lambda **_kwargs: fixture.protected.parent.parent,
    )

    def replace_parent_then_write(
        *,
        entry: object,
        reference: object,
        binding: Callable[[], str | None],
        write: Callable[..., CommitOutcome],
    ) -> dict[str, object]:
        _ = (entry, reference)
        assert binding() is None
        fixture.destination.parent.rmdir()
        fixture.destination.parent.symlink_to(fixture.protected.parent, target_is_directory=True)
        return commit_status_result(outcome=write(value=b"must-not-reach-protected-path"))

    monkeypatch.setattr(target_service, "provisioning_result", replace_parent_then_write)
    held = take_lock(
        path=target_lock_path(state_dir=fixture.state_dir, target_ref=_REFERENCE),
        owner_uid=os.getuid(),
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    ).unwrap()
    try:
        outcome = target_service.target_role_result(
            role_name="final-provisioning",
            members={
                "version": 1,
                "target_ref": _REFERENCE,
                "consumer_run_id": "run-review-two",
                "record_id": _RECORD,
                "value_generation": _GENERATION,
                "value_ref": (
                    "op://llm-provider-manager-token-values/" f"{_RECORD}-{_GENERATION}/credential"
                ),
                "lease_expires_at": _EXPIRES,
                "external_call_timeout_seconds": 30,
                "op_executable": "/usr/bin/op",
            },
            environ={},
            lock_descriptor=held.descriptor,
        )
    finally:
        release_lock(held=held)

    assert outcome == {"version": 1, "status": UNCOMMITTED, "committed_at": None}
    assert fixture.protected.read_bytes() == b"interactive-credential"


def test_definite_prewrite_store_failure_is_cleanup_safe_and_drives_cleanup(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = importlib.import_module("_lpm_runtime_backend")
    monkeypatch.setattr(backend, "runtime_prerequisites", _prerequisites_ok)
    state_dir = tmp_path / "state"
    ports = RolePorts(
        config=default_config(),
        owner_uid=os.getuid(),
        state_dir=state_dir,
        environ={"PATH": "/usr/bin:/bin"},
        launch=_Completion(stdout=b'{"version":1,"status":"store-unavailable"}'),
        python_executable=sys.executable,
        packaged_companion=str(tmp_path / "_lpm_companion.py"),
    )
    role_result = ports(
        request=_request(),
        destination=str(tmp_path / "destination"),
        lock=_target_lock(state_dir=state_dir),
    )
    assert isinstance(role_result, Failure)
    failure = role_result.failure()
    assert failure.error_type == "store-unavailable"
    assert failure.cleanup_safe is True

    request = ProvisionRequest(
        provider="anthropic",
        kind="claude-code-oauth",
        purpose="factory",
        consumer_run_id="run-review-two",
        target_ref=_REFERENCE,
        strategy="consume-first",
        lease_seconds=3600,
    )
    operation = OperationRecord(
        operation_id="20000000-0000-4000-8000-000000000002",
        command="provision",
        phase="start",
        idempotency_key="f" * 64,
        accepted_at=_NOW,
        normalized_input={},
        terminal_result=None,
        ordered_effects=("target-write",),
        completed_step=-1,
    )
    cleanups: list[str] = []

    def cleanup(**_kwargs: object) -> Success[None]:
        cleanups.append("cleaned")
        return Success(None)

    driven = drive_provision_phase(
        host=_DriveHost(
            state_dir=state_dir,
            owner_uid=os.getuid(),
            config=default_config(),
            store=InMemorySecretStore(),
        ),
        request=request,
        operation=operation,
        inputs=EffectInputs(),
        ports=ProvisionDrivePorts(
            drive=lambda **_kwargs: Failure(failure),
            read_assignment=pytest.fail,
            cleanup_failed=cleanup,
        ),
    )

    assert isinstance(driven, Failure)
    assert driven.failure() == failure
    assert cleanups == ["cleaned"]
