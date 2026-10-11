"""Durable phase driving for a prepared provisioning operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment
from _lpm_engine_context import EffectInputs, OperationEngine
from _lpm_operation import OperationRecord
from _lpm_operation_plan import PlanContext
from _lpm_provision_request import ProvisionRequest
from _lpm_results import PROVISIONING_FAILED, ManagerError, store_unavailable
from _lpm_runtime_base import ProvisionRuntimeHost, engine_for

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "DriveOperation",
    "ProvisionDrivePorts",
    "drive_provision_phase",
]


class DriveOperation(Protocol):
    """The operation transition port injected by the installed coordinator."""

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


class AssignmentReader(Protocol):
    """Read the authoritative assignment after postcommit completes."""

    def __call__(
        self, *, host: ProvisionRuntimeHost, consumer_run_id: str
    ) -> Result[Assignment | None, ManagerError]: ...


class FailedStartCleanup(Protocol):
    """Discard only a start proven to have failed before its target write."""

    def __call__(
        self, *, host: ProvisionRuntimeHost, operation: OperationRecord, inputs: EffectInputs
    ) -> Result[None, ManagerError]: ...


@dataclass(frozen=True, kw_only=True)
class ProvisionDrivePorts:
    """Fault-injectable collaborators for durable phase driving."""

    drive: DriveOperation
    read_assignment: AssignmentReader
    cleanup_failed: FailedStartCleanup


def drive_provision_phase(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    operation: OperationRecord,
    inputs: EffectInputs,
    ports: ProvisionDrivePorts,
) -> Result[dict[str, object], ManagerError]:
    """Drive start and postcommit, returning the committed assignment receipt."""
    current = operation
    if current.phase == "start":
        started = ports.drive(
            engine=engine_for(host=host),
            operation=current,
            inputs=inputs,
            condition="target-committed",
            context=PlanContext(),
            terminal_result=None,
        )
        if isinstance(started, Failure):
            return _failed_start(
                host=host,
                operation=current,
                inputs=inputs,
                error=started.failure(),
                cleanup_failed=ports.cleanup_failed,
            )
        following = started.unwrap()
        if following is None:
            return Failure(store_unavailable(message="provision start lost its postcommit phase"))
        current = following
    finished = ports.drive(
        engine=engine_for(host=host),
        operation=current,
        inputs=inputs,
        condition="every-effect-committed",
        context=PlanContext(),
        terminal_result=None,
    )
    if isinstance(finished, Failure):
        return Failure(finished.failure())
    assigned = ports.read_assignment(host=host, consumer_run_id=request.consumer_run_id)
    if isinstance(assigned, Failure):
        return Failure(assigned.failure())
    assignment = assigned.unwrap()
    if assignment is None:
        return Failure(store_unavailable(message="provision committed without an assignment"))
    return Success({"operation": "provision", "receipt": dict(assignment.receipt)})


def _failed_start(
    *,
    host: ProvisionRuntimeHost,
    operation: OperationRecord,
    inputs: EffectInputs,
    error: ManagerError,
    cleanup_failed: FailedStartCleanup,
) -> Result[dict[str, object], ManagerError]:
    if error.error_type != PROVISIONING_FAILED and not error.cleanup_safe:
        return Failure(error)
    cleaned = cleanup_failed(host=host, operation=operation, inputs=inputs)
    return Failure(cleaned.failure() if isinstance(cleaned, Failure) else error)
