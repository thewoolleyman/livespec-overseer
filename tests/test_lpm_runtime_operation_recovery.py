"""The command runtime resumes durable target and provision phases."""

from __future__ import annotations

import importlib
import os
import pathlib
from dataclasses import replace
from types import ModuleType

import pytest

from overseer._lpm_engine_context import (
    EffectInputs,
    OperationEngine,
    ProvisionInputs,
    SelectedCredential,
    TargetInputs,
)
from overseer._lpm_operation import OperationRecord
from overseer._lpm_results import ManagerError, provisioning_failed, store_unavailable
from overseer._lpm_runtime_recovery import recover_provision_phase, recover_target_phase
from overseer._lpm_store import InMemorySecretStore
from overseer._lpm_target import TargetLock
from overseer._vendor.returns.result import Failure, Success

__all__: list[str] = []

_TARGET_OPERATION_ID = "5f1c7a28-9b0d-4c6e-8a31-2d4b6e8a0c13"
_PROVISION_OPERATION_ID = "7a3d1e52-6c8b-4f0a-9d27-3e5c7b9f1a46"
_RECORD_ID = "8d4f2a60-5e91-43c7-b2a8-1f6c0d3e5b72"
_GENERATION = "9e5a3b71-6f02-44d8-a3b9-2c7d1e4f6a83"
_DEPENDENCY_FAILURE = store_unavailable(message="recovery dependency unavailable")
_START_FAILURE = provisioning_failed(message="target definitely refused the write")


def _fail_dependency(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(_DEPENDENCY_FAILURE)


def _fail_start(**_kwargs: object) -> Failure[ManagerError]:
    return Failure(_START_FAILURE)


def _module(*, name: str) -> ModuleType:
    return importlib.import_module(name)


def _engine(*, state_dir: pathlib.Path) -> OperationEngine:
    return OperationEngine(
        state_dir=state_dir,
        owner_uid=os.getuid(),
        store=InMemorySecretStore(),
    )


def _write_operation(*, state_dir: pathlib.Path, operation: OperationRecord) -> None:
    store = _module(name="_lpm_operation_store")
    path = store.operation_path(
        state_dir=state_dir,
        command=operation.command,
        idempotency_key=operation.idempotency_key,
    ).unwrap()
    assert isinstance(
        store.write_operation(path=path, operation=operation, owner_uid=os.getuid()), Success
    )


def _record_path(
    *, state_dir: pathlib.Path, family: str, identity: tuple[str, ...]
) -> pathlib.Path:
    return (
        _module(name="_lpm_paths")
        .local_record_path(state_dir=state_dir, family=family, identity=identity)
        .unwrap()
    )


def _target_operation() -> OperationRecord:
    return OperationRecord(
        operation_id=_TARGET_OPERATION_ID,
        command="target",
        phase="issue",
        idempotency_key="c" * 64,
        accepted_at="2026-10-02T09:15:00Z",
        normalized_input={
            "version": 1,
            "consumer_run_id": "run-target",
            "adapter": "isolated-run",
        },
        terminal_result=None,
        ordered_effects=("issuance-create", "registration-remove"),
        completed_step=-1,
    )


def _provision_operation(*, key: str) -> OperationRecord:
    return OperationRecord(
        operation_id=_PROVISION_OPERATION_ID,
        command="provision",
        phase="start",
        idempotency_key=key,
        accepted_at="2026-10-02T11:00:00Z",
        normalized_input={
            "version": 1,
            "provider": "anthropic",
            "kind": "claude-code-oauth",
            "purpose": "factory",
            "consumer_run_id": f"run-{key[0]}",
            "target_ref": f"ref-{key[0]}",
            "strategy": "consume-first",
            "lease_seconds": 3600,
        },
        terminal_result=None,
        ordered_effects=("lease-create", "prepared-assignment-create", "target-write"),
        completed_step=-1,
    )


def _provision_inputs(*, tmp_path: pathlib.Path, fence_now: str) -> EffectInputs:
    return EffectInputs(
        provision=ProvisionInputs(
            selected=SelectedCredential(
                account_id="account-primary",
                record_id=_RECORD_ID,
                value_generation=_GENERATION,
                value_ref=f"op://values/{_GENERATION}/credential",
                receipt={
                    "record_id": _RECORD_ID,
                    "account_id": "account-primary",
                    "purpose": "factory",
                    "validated_at": "2026-10-02T10:00:00Z",
                    "lease_expires_at": "2026-10-02T12:00:00Z",
                },
            ),
            credential_value=b"credential-never-rendered",
            destination=str(tmp_path / "target" / "credential"),
            lock=TargetLock(
                path=tmp_path / "target.lock",
                timeout_seconds=1.0,
                monotonic=lambda: 0.0,
                sleep=lambda _seconds: None,
            ),
            fence_now=fence_now,
        )
    )


def _existing_target(*, root: pathlib.Path) -> pathlib.Path:
    root.mkdir(mode=0o700)
    destination = root / "target" / "credential"
    destination.parent.mkdir(parents=True, mode=0o700)
    _ = destination.write_bytes(b"prior-target")
    destination.chmod(0o600)
    return destination


def test_target_and_provision_runtime_recover_persisted_phases_and_typed_failure(
    tmp_path: pathlib.Path,
) -> None:
    module_path = pathlib.Path(__file__).parents[1] / "overseer" / "_lpm_runtime_recovery.py"
    assert module_path.is_file(), "the installed runtime recovery composer must exist"
    local = _module(name="_lpm_localstate")

    target_state = tmp_path / "target-state"
    target_state.mkdir(mode=0o700)
    target_operation = _target_operation()
    _write_operation(state_dir=target_state, operation=target_operation)
    registration = _record_path(
        state_dir=target_state, family="run-registration", identity=("run-target",)
    )
    assert isinstance(
        local.write_local_record(
            path=registration,
            value={"version": 1, "consumer_run_id": "run-target"},
            owner_uid=os.getuid(),
        ),
        Success,
    )
    target_inputs = EffectInputs(
        target=TargetInputs(
            reference="ref-target",
            adapter="isolated-run",
            isolated_root="/run",
            destination="/run/target",
        )
    )
    recovered_target = recover_target_phase(
        engine=_engine(state_dir=target_state),
        idempotency_key=target_operation.idempotency_key,
        inputs=target_inputs,
    )
    assert isinstance(recovered_target, Success)
    assert recovered_target.unwrap() is None
    assert not registration.exists()

    provision_state = tmp_path / "provision-state"
    provision_state.mkdir(mode=0o700)
    provision = _provision_operation(key="e" * 64)
    _write_operation(state_dir=provision_state, operation=provision)
    failed_root = tmp_path / "failed"
    destination = _existing_target(root=failed_root)
    failed_inputs = _provision_inputs(tmp_path=failed_root, fence_now="2026-10-02T12:00:00Z")
    refused = recover_provision_phase(
        engine=_engine(state_dir=provision_state),
        idempotency_key=provision.idempotency_key,
        inputs=failed_inputs,
    )
    assert isinstance(refused, Failure)
    assert refused.failure().error_type == "provisioning-failed"
    assert destination.read_bytes() == b"prior-target"
    assert not _record_path(
        state_dir=provision_state, family="assignment", identity=("run-e",)
    ).exists()
    assert not _record_path(
        state_dir=provision_state, family="lease", identity=("anthropic", "account-primary")
    ).exists()


def test_recovery_returns_typed_no_pending_failure_and_all_drive_outcomes(
    tmp_path: pathlib.Path,
) -> None:
    empty_engine = _engine(state_dir=tmp_path / "empty")
    target_inputs = EffectInputs(
        target=TargetInputs(
            reference="ref-target",
            adapter="isolated-run",
            isolated_root="/run",
            destination="/run/target",
        )
    )
    missing_target = recover_target_phase(
        engine=empty_engine,
        idempotency_key="a" * 64,
        inputs=target_inputs,
    )
    missing_provision = recover_provision_phase(
        engine=empty_engine,
        idempotency_key="b" * 64,
        inputs=EffectInputs(),
    )
    assert isinstance(missing_target, Failure)
    assert missing_target.failure().error_type == "store-unavailable"
    assert isinstance(missing_provision, Failure)
    assert missing_provision.failure().error_type == "store-unavailable"

    failed_target = recover_target_phase(
        engine=empty_engine,
        idempotency_key="c" * 64,
        inputs=target_inputs,
        operation=_target_operation(),
        drive=_fail_dependency,
    )
    assert isinstance(failed_target, Failure)
    assert failed_target.failure() == _DEPENDENCY_FAILURE

    provision = _provision_operation(key="d" * 64)
    postcommit = replace(
        provision,
        phase="postcommit",
        ordered_effects=("assignment-commit", "selection-update", "proof-update"),
    )
    conditions: list[str] = []

    def finish_provision(**kwargs: object) -> Success[OperationRecord | None]:
        conditions.append(str(kwargs["condition"]))
        return Success(postcommit if len(conditions) == 1 else None)

    recovered_provision = recover_provision_phase(
        engine=empty_engine,
        idempotency_key=provision.idempotency_key,
        inputs=EffectInputs(),
        operation=provision,
        drive=finish_provision,
    )
    assert isinstance(recovered_provision, Success)
    assert recovered_provision.unwrap() is None
    assert conditions == ["target-committed", "every-effect-committed"]


def test_recovery_dependency_failures_remain_typed(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import overseer._lpm_runtime_recovery as recovery

    engine = _engine(state_dir=tmp_path / "dependencies")
    target_inputs = EffectInputs(
        target=TargetInputs(
            reference="ref-target",
            adapter="isolated-run",
            isolated_root="/run",
            destination="/run/target",
        )
    )
    with monkeypatch.context() as context:
        context.setattr(recovery, "pending_operation", _fail_dependency)
        failed_pending_target = recover_target_phase(
            engine=engine,
            idempotency_key="e" * 64,
            inputs=target_inputs,
        )
        failed_pending_provision = recover_provision_phase(
            engine=engine,
            idempotency_key="f" * 64,
            inputs=EffectInputs(),
        )
    assert isinstance(failed_pending_target, Failure)
    assert failed_pending_target.failure() == _DEPENDENCY_FAILURE
    assert isinstance(failed_pending_provision, Failure)
    assert failed_pending_provision.failure() == _DEPENDENCY_FAILURE

    provision = _provision_operation(key="d" * 64)
    failed_cleanup = recover_provision_phase(
        engine=engine,
        idempotency_key=provision.idempotency_key,
        inputs=EffectInputs(),
        operation=provision,
        drive=_fail_start,
        cleanup_failed=_fail_dependency,
    )
    assert isinstance(failed_cleanup, Failure)
    assert failed_cleanup.failure() == _DEPENDENCY_FAILURE


@pytest.mark.parametrize(
    "defect",
    [
        "pending-failure",
        "pending-missing",
        "path-failure",
        "transition-failure",
        "transition-missing",
    ],
)
def test_recovery_cleanup_dependency_failures_remain_typed(
    *, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    import overseer._lpm_runtime_recovery as recovery

    engine = _engine(state_dir=tmp_path / defect)
    provision = _provision_operation(key="d" * 64)
    with monkeypatch.context() as context:
        context.setattr(recovery, "pending_operation", lambda **_kwargs: Success(provision))
        if defect == "pending-failure":
            context.setattr(recovery, "pending_operation", _fail_dependency)
        elif defect == "pending-missing":
            context.setattr(recovery, "pending_operation", lambda **_kwargs: Success(None))
        elif defect == "path-failure":
            context.setattr(recovery, "operation_path", _fail_dependency)
        elif defect == "transition-failure":
            context.setattr(recovery, "transition_operation", _fail_dependency)
        else:
            context.setattr(recovery, "transition_operation", lambda **_kwargs: Success(None))
        outcome = recover_provision_phase(
            engine=engine,
            idempotency_key=provision.idempotency_key,
            inputs=EffectInputs(),
            operation=provision,
            drive=_fail_start,
        )
    assert isinstance(outcome, Failure)
