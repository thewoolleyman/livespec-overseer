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
from _lpm_results import ManagerError, store_unavailable
from _lpm_runtime_base import ProvisionRuntimeHost, engine_for
from _lpm_runtime_recovery import recover_provision_phase

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

    def cleanup_failed(
        *, operation: OperationRecord, inputs: EffectInputs
    ) -> Result[None, ManagerError]:
        return ports.cleanup_failed(host=host, operation=operation, inputs=inputs)

    recovered = recover_provision_phase(
        engine=engine_for(host=host),
        idempotency_key=operation.idempotency_key,
        operation=operation,
        inputs=inputs,
        drive=ports.drive,
        cleanup_failed=cleanup_failed,
    )
    if isinstance(recovered, Failure):
        return Failure(recovered.failure())
    assigned = ports.read_assignment(host=host, consumer_run_id=request.consumer_run_id)
    if isinstance(assigned, Failure):
        return Failure(assigned.failure())
    assignment = assigned.unwrap()
    if assignment is None:
        return Failure(store_unavailable(message="provision committed without an assignment"))
    return Success({"operation": "provision", "receipt": dict(assignment.receipt)})
