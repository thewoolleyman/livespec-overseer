"""Serialized provision command coordination over durable recovery."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_assignment import Assignment
from _lpm_engine import drive_operation, pending_operation
from _lpm_locks import release_lock
from _lpm_operation import OperationRecord
from _lpm_operation_identity import idempotency_key_for
from _lpm_provision_request import ProvisionRequest, provision_request_object
from _lpm_results import ManagerError, invalid_request
from _lpm_runtime_base import ProvisionRuntimeHost, engine_for, run_lock
from _lpm_runtime_bindings import read_runtime_assignment
from _lpm_runtime_provision_recovery import fresh_provision, resume_provision

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "run_provision",
]


def run_provision(
    *, host: ProvisionRuntimeHost, request: ProvisionRequest
) -> Result[dict[str, object], ManagerError]:
    """Serialize a run's complete authoritative read, recovery, and fresh attempt."""
    held = run_lock(host=host, consumer_run_id=request.consumer_run_id)
    if isinstance(held, Failure):
        return Failure(held.failure())
    try:
        return _serialized(host=host, request=request)
    finally:
        release_lock(held=held.unwrap())


def _serialized(
    *, host: ProvisionRuntimeHost, request: ProvisionRequest
) -> Result[dict[str, object], ManagerError]:
    normalized = provision_request_object(request=request)
    state = _provision_state(host=host, request=request, normalized=normalized)
    if isinstance(state, Failure):
        return Failure(state.failure())
    operation, assignment = state.unwrap()
    if operation is not None:
        resumed = resume_provision(
            host=host,
            request=request,
            operation=operation,
            assignment=assignment,
            drive=drive_operation,
        )
        if isinstance(resumed, Failure):
            return Failure(resumed.failure())
        payload = resumed.unwrap()
        if payload is not None:
            return Success(payload)
        assignment = None
    if assignment is not None:
        return Success(_payload(assignment=assignment))
    return fresh_provision(host=host, request=request, normalized=normalized, drive=drive_operation)


def _provision_state(
    *, host: ProvisionRuntimeHost, request: ProvisionRequest, normalized: dict[str, object]
) -> Result[tuple[OperationRecord | None, Assignment | None], ManagerError]:
    key = idempotency_key_for(
        command="provision", identity={"consumer_run_id": request.consumer_run_id}
    )
    if isinstance(key, Failure):
        return Failure(key.failure())
    pending = pending_operation(
        engine=engine_for(host=host), command="provision", idempotency_key=key.unwrap()
    )
    if isinstance(pending, Failure):
        return Failure(pending.failure())
    operation = pending.unwrap()
    if operation is not None and operation.normalized_input != normalized:
        return Failure(invalid_request(message="a different provision request is pending"))
    assigned = read_runtime_assignment(host=host, consumer_run_id=request.consumer_run_id)
    if isinstance(assigned, Failure):
        return Failure(assigned.failure())
    assignment = assigned.unwrap()
    if assignment is not None and assignment.request != normalized:
        return Failure(invalid_request(message="this run is assigned a different request"))
    return Success((operation, assignment))


def _payload(*, assignment: Assignment) -> dict[str, object]:
    return {"operation": "provision", "receipt": dict(assignment.receipt)}
