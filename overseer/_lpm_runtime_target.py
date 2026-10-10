"""Concrete target command composition over the durable operation engine."""

from __future__ import annotations

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine import drive_operation, pending_operation
from _lpm_engine_context import EffectInputs, TargetInputs
from _lpm_locks import release_lock
from _lpm_operation import OperationRecord
from _lpm_operation_identity import idempotency_key_for
from _lpm_operation_plan import PlanContext
from _lpm_results import ManagerError, invalid_request, store_unavailable
from _lpm_runtime_base import (
    RuntimeHost,
    engine_for,
    new_operation,
    run_lock,
    target_destination,
    write_new_operation,
)
from _lpm_runtime_issuance import (
    existing_issuance_payload,
    issuance_for_run,
    read_runtime_issuance,
)

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "run_target",
]


def run_target(
    *, host: RuntimeHost, normalized_input: dict[str, object]
) -> Result[dict[str, object], ManagerError]:
    """Recover or durably issue the one target reference for this run."""
    run_id = str(normalized_input["consumer_run_id"])
    held = run_lock(host=host, consumer_run_id=run_id)
    if isinstance(held, Failure):
        return Failure(held.failure())
    try:
        return _serialized(host=host, normalized_input=normalized_input)
    finally:
        release_lock(held=held.unwrap())


def _serialized(
    *, host: RuntimeHost, normalized_input: dict[str, object]
) -> Result[dict[str, object], ManagerError]:
    key = idempotency_key_for(
        command="target", identity={"consumer_run_id": str(normalized_input["consumer_run_id"])}
    )
    if isinstance(key, Failure):
        return Failure(key.failure())
    engine = engine_for(host=host)
    pending = pending_operation(engine=engine, command="target", idempotency_key=key.unwrap())
    if isinstance(pending, Failure):
        return Failure(pending.failure())
    operation = pending.unwrap()
    if operation is not None:
        return _recover(host=host, operation=operation, normalized_input=normalized_input)
    return _fresh(host=host, normalized_input=normalized_input)


def _recover(
    *, host: RuntimeHost, operation: OperationRecord, normalized_input: dict[str, object]
) -> Result[dict[str, object], ManagerError]:
    if operation.normalized_input != normalized_input:
        return Failure(invalid_request(message="a different target request is pending"))
    return _drive(host=host, operation=operation)


def _fresh(
    *, host: RuntimeHost, normalized_input: dict[str, object]
) -> Result[dict[str, object], ManagerError]:
    existing = issuance_for_run(host=host, consumer_run_id=str(normalized_input["consumer_run_id"]))
    if isinstance(existing, Failure):
        return Failure(existing.failure())
    issued = existing.unwrap()
    if issued is not None:
        return existing_issuance_payload(
            host=host, issuance=issued, requested_adapter=str(normalized_input["adapter"])
        )
    created = new_operation(
        host=host,
        command="target",
        phase="issue",
        normalized_input=normalized_input,
        context=PlanContext(),
    )
    if isinstance(created, Failure):
        return Failure(created.failure())
    written = write_new_operation(host=host, operation=created.unwrap())
    if isinstance(written, Failure):
        return Failure(written.failure())
    return _drive(host=host, operation=written.unwrap())


def _drive(
    *, host: RuntimeHost, operation: OperationRecord
) -> Result[dict[str, object], ManagerError]:
    reference = operation.operation_id
    driven = drive_operation(
        engine=engine_for(host=host),
        operation=operation,
        inputs=EffectInputs(
            target=TargetInputs(
                reference=reference,
                adapter=str(operation.normalized_input["adapter"]),
                destination=str(target_destination(state_dir=host.state_dir, reference=reference)),
            )
        ),
        condition="every-effect-committed",
        context=PlanContext(),
        terminal_result=None,
    )
    if isinstance(driven, Failure):
        return Failure(driven.failure())
    issued = read_runtime_issuance(host=host, reference=reference)
    if isinstance(issued, Failure):
        return Failure(issued.failure())
    issuance = issued.unwrap()
    if issuance is None:
        return Failure(store_unavailable(message="target issue committed without an issuance"))
    return Success(
        {
            "operation": "target",
            "target_ref": issuance.reference,
            "expires_at": issuance.expires_at,
        }
    )
