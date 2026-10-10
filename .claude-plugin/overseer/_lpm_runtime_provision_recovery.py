"""Fresh provision execution and interrupted-phase recovery."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment
from _lpm_engine import drive_operation
from _lpm_engine_context import EffectInputs, SelectedCredential
from _lpm_operation import OperationRecord
from _lpm_operation_plan import PlanContext
from _lpm_provision_request import ProvisionRequest
from _lpm_results import PROVISIONING_FAILED, ManagerError
from _lpm_runtime_base import (
    ProvisionRuntimeHost,
    new_operation,
    write_new_operation,
)
from _lpm_runtime_bindings import read_runtime_assignment
from _lpm_runtime_issuance import resolved_runtime_issuance
from _lpm_runtime_provision_drive import (
    DriveOperation,
    ProvisionDrivePorts,
    drive_provision_phase,
)
from _lpm_runtime_provision_effects import (
    cleanup_failed_start,
    finish_provision_cleanup,
    provision_effect_inputs,
)
from _lpm_runtime_selection import selected_for_request, selected_from_assignment

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "fresh_provision",
    "resume_provision",
]


def fresh_provision(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    normalized: dict[str, object],
    drive: DriveOperation = drive_operation,
) -> Result[dict[str, object], ManagerError]:
    """Select, persist, and drive one fresh provisioning operation."""
    first_now = host.capture_time()
    issuance = resolved_runtime_issuance(host=host, request=request, bound=False, now=first_now)
    if isinstance(issuance, Failure):
        return Failure(issuance.failure())
    prepared = _fresh_selection(
        host=host,
        request=request,
        normalized=normalized,
        first_now=first_now,
    )
    if isinstance(prepared, Failure):
        return Failure(prepared.failure())
    operation, selected = prepared.unwrap()
    written = write_new_operation(host=host, operation=operation)
    if isinstance(written, Failure):
        return Failure(written.failure())
    inputs = provision_effect_inputs(
        host=host,
        request=request,
        selected=selected,
        destination=issuance.unwrap().destination,
    )
    if isinstance(inputs, Failure):
        return Failure(inputs.failure())
    return drive_provision(
        host=host,
        request=request,
        operation=written.unwrap(),
        inputs=inputs.unwrap(),
        drive=drive,
    )


def resume_provision(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    operation: OperationRecord,
    assignment: Assignment | None,
    drive: DriveOperation = drive_operation,
) -> Result[dict[str, object] | None, ManagerError]:
    """Finish retained cleanup or resume the exact prepared selection."""
    if operation.phase == "cleanup":
        return _resume_cleanup(
            host=host, request=request, operation=operation, assignment=assignment
        )
    selected = (
        selected_for_request(host=host, request=request, now=operation.accepted_at)
        if assignment is None
        else Success(selected_from_assignment(assignment=assignment))
    )
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    inputs = provision_effect_inputs(
        host=host,
        request=request,
        selected=selected.unwrap(),
        recovering=assignment is not None,
    )
    if isinstance(inputs, Failure):
        return Failure(inputs.failure())
    driven = drive_provision(
        host=host,
        request=request,
        operation=operation,
        inputs=inputs.unwrap(),
        drive=drive,
    )
    if isinstance(driven, Failure) and driven.failure().error_type == PROVISIONING_FAILED:
        return Success(None)
    return driven


def drive_provision(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    operation: OperationRecord,
    inputs: EffectInputs,
    drive: DriveOperation = drive_operation,
) -> Result[dict[str, object], ManagerError]:
    """Drive start and postcommit, returning the committed assignment receipt."""
    return drive_provision_phase(
        host=host,
        request=request,
        operation=operation,
        inputs=inputs,
        ports=ProvisionDrivePorts(
            drive=drive,
            read_assignment=read_runtime_assignment,
            cleanup_failed=cleanup_failed_start,
        ),
    )


def _fresh_selection(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    normalized: dict[str, object],
    first_now: str,
) -> Result[tuple[OperationRecord, SelectedCredential], ManagerError]:
    selected = selected_for_request(host=host, request=request, now=first_now)
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    created = new_operation(
        host=host,
        command="provision",
        phase="start",
        normalized_input=normalized,
        context=PlanContext(),
    )
    if isinstance(created, Failure):
        return Failure(created.failure())
    operation = created.unwrap()
    if operation.accepted_at == first_now:
        return Success((operation, selected.unwrap()))
    reselection = selected_for_request(host=host, request=request, now=operation.accepted_at)
    if isinstance(reselection, Failure):
        return Failure(reselection.failure())
    return Success((operation, reselection.unwrap()))


def _resume_cleanup(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    operation: OperationRecord,
    assignment: Assignment | None,
) -> Result[dict[str, object] | None, ManagerError]:
    selected = (
        selected_for_request(host=host, request=request, now=host.capture_time())
        if assignment is None
        else Success(selected_from_assignment(assignment=assignment))
    )
    if isinstance(selected, Failure):
        return Failure(selected.failure())
    inputs = provision_effect_inputs(host=host, request=request, selected=selected.unwrap())
    if isinstance(inputs, Failure):
        return Failure(inputs.failure())
    cleaned = finish_provision_cleanup(
        host=host,
        operation=operation,
        inputs=inputs.unwrap(),
        prepared=assignment is not None,
    )
    if isinstance(cleaned, Failure):
        return Failure(cleaned.failure())
    return Success(None)
