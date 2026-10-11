"""Compose durable operation replay into the installed command runtime."""

from __future__ import annotations

from typing import Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine import drive_operation, pending_operation
from _lpm_engine_context import EffectInputs, OperationEngine
from _lpm_operation import OperationRecord
from _lpm_operation_plan import PlanContext
from _lpm_operation_store import operation_path, transition_operation
from _lpm_results import PROVISIONING_FAILED, ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "recover_provision_phase",
    "recover_target_phase",
]


class _DriveOperation(Protocol):
    def __call__(
        self,
        *,
        engine: OperationEngine,
        operation: OperationRecord,
        inputs: EffectInputs,
        condition: str,
        context: PlanContext,
        terminal_result: dict[str, object] | None,
    ) -> Result[OperationRecord | None, ManagerError]: ...


class _FailedStartCleanup(Protocol):
    def __call__(
        self, *, operation: OperationRecord, inputs: EffectInputs
    ) -> Result[None, ManagerError]: ...


def recover_target_phase(
    *,
    engine: OperationEngine,
    idempotency_key: str,
    inputs: EffectInputs,
    operation: OperationRecord | None = None,
    drive: _DriveOperation = drive_operation,
) -> Result[OperationRecord | None, ManagerError]:
    """Replay one durable target phase without unwrapping either result rail."""
    standing = _standing_operation(
        engine=engine,
        command="target",
        idempotency_key=idempotency_key,
        operation=operation,
    )
    if isinstance(standing, Failure):
        return Failure(standing.failure())
    current = standing.unwrap()
    if current is None:
        return Failure(store_unavailable(message="no pending target operation to recover"))
    return drive(
        engine=engine,
        operation=current,
        inputs=inputs,
        condition="every-effect-committed",
        context=PlanContext(),
        terminal_result=None,
    )


def recover_provision_phase(
    *,
    engine: OperationEngine,
    idempotency_key: str,
    inputs: EffectInputs,
    operation: OperationRecord | None = None,
    drive: _DriveOperation = drive_operation,
    cleanup_failed: _FailedStartCleanup | None = None,
) -> Result[OperationRecord | None, ManagerError]:
    """Replay start and postcommit while retaining every ambiguous target outcome."""
    standing = _standing_operation(
        engine=engine,
        command="provision",
        idempotency_key=idempotency_key,
        operation=operation,
    )
    if isinstance(standing, Failure):
        return Failure(standing.failure())
    current = standing.unwrap()
    if current is None:
        return Failure(store_unavailable(message="no pending provision operation to recover"))
    if current.phase == "start":
        started = drive(
            engine=engine,
            operation=current,
            inputs=inputs,
            condition="target-committed",
            context=PlanContext(),
            terminal_result=None,
        )
        if isinstance(started, Failure):
            return _failed_provision_start(
                engine=engine,
                operation=current,
                inputs=inputs,
                error=started.failure(),
                drive=drive,
                cleanup_failed=cleanup_failed,
            )
        following = started.unwrap()
        if following is None:
            return Failure(store_unavailable(message="provision start lost its postcommit phase"))
        current = following
    return drive(
        engine=engine,
        operation=current,
        inputs=inputs,
        condition="every-effect-committed",
        context=PlanContext(prepared_state_exists=current.phase == "cleanup"),
        terminal_result=None,
    )


def _standing_operation(
    *,
    engine: OperationEngine,
    command: str,
    idempotency_key: str,
    operation: OperationRecord | None,
) -> Result[OperationRecord | None, ManagerError]:
    if operation is not None:
        return Result.from_value(operation)
    return pending_operation(engine=engine, command=command, idempotency_key=idempotency_key)


def _failed_provision_start(
    *,
    engine: OperationEngine,
    operation: OperationRecord,
    inputs: EffectInputs,
    error: ManagerError,
    drive: _DriveOperation,
    cleanup_failed: _FailedStartCleanup | None,
) -> Result[OperationRecord | None, ManagerError]:
    if error.error_type != PROVISIONING_FAILED and not error.cleanup_safe:
        return Failure(error)
    if cleanup_failed is None:
        cleaned = _cleanup_failed_provision(
            engine=engine,
            operation=operation,
            inputs=inputs,
            drive=drive,
        )
    else:
        cleaned = cleanup_failed(operation=operation, inputs=inputs)
    if isinstance(cleaned, Failure):
        return Failure(cleaned.failure())
    return Failure(error)


def _cleanup_failed_provision(
    *,
    engine: OperationEngine,
    operation: OperationRecord,
    inputs: EffectInputs,
    drive: _DriveOperation,
) -> Result[OperationRecord | None, ManagerError]:
    standing = pending_operation(
        engine=engine,
        command="provision",
        idempotency_key=operation.idempotency_key,
    )
    if isinstance(standing, Failure):
        return Failure(standing.failure())
    current = standing.unwrap()
    if current is None:
        return Failure(store_unavailable(message="the failed provision operation disappeared"))
    path = operation_path(
        state_dir=engine.state_dir,
        command=current.command,
        idempotency_key=current.idempotency_key,
    )
    if isinstance(path, Failure):
        return Failure(path.failure())
    installed = transition_operation(
        path=path.unwrap(),
        operation=current,
        condition="pre-commit-failure",
        context=PlanContext(prepared_state_exists=True),
        terminal_result=None,
        owner_uid=engine.owner_uid,
    )
    if isinstance(installed, Failure):
        return Failure(installed.failure())
    cleanup = installed.unwrap()
    if cleanup is None:
        return Failure(store_unavailable(message="provision cleanup was not installed"))
    return drive(
        engine=engine,
        operation=cleanup,
        inputs=inputs,
        condition="every-effect-committed",
        context=PlanContext(prepared_state_exists=True),
        terminal_result=None,
    )
