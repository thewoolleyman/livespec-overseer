"""Provision effect inputs, final-provisioning boundary, and cleanup transitions."""

from __future__ import annotations

from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine import drive_operation, pending_operation
from _lpm_engine_context import EffectInputs, ProvisionInputs, SelectedCredential
from _lpm_operation import OperationRecord
from _lpm_operation_plan import PlanContext
from _lpm_operation_store import operation_path, transition_operation
from _lpm_provision_request import ProvisionRequest
from _lpm_results import ManagerError, store_unavailable
from _lpm_runtime_base import ProvisionRuntimeHost, engine_for, target_lock
from _lpm_runtime_issuance import resolved_runtime_issuance
from _lpm_runtime_roles import FinalProvisioningRequest, TargetStatusRequest
from _lpm_target import CommitOutcome

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "cleanup_failed_start",
    "finish_provision_cleanup",
    "provision_effect_inputs",
]


@dataclass(frozen=True, kw_only=True)
class _ProvisioningCall:
    """Bind selected metadata to the isolated role without ever owning its value."""

    host: ProvisionRuntimeHost
    request: ProvisionRequest
    selected: SelectedCredential
    destination: str
    recovering: bool

    def __call__(self, *, lease_expires_at: str) -> Result[CommitOutcome, ManagerError]:
        lock = target_lock(host=self.host, target_ref=self.request.target_ref)
        if self.recovering and self.host.target_status is not None:
            return self.host.target_status(
                request=TargetStatusRequest(
                    target_ref=self.request.target_ref,
                    consumer_run_id=self.request.consumer_run_id,
                    value_generation=self.selected.value_generation,
                ),
                destination=self.destination,
                lock=lock,
            )
        return self.host.provision_target(
            request=FinalProvisioningRequest(
                target_ref=self.request.target_ref,
                consumer_run_id=self.request.consumer_run_id,
                record_id=self.selected.record_id,
                value_generation=self.selected.value_generation,
                value_ref=self.selected.value_ref,
                lease_expires_at=lease_expires_at,
                external_call_timeout_seconds=self.host.config.external_call_timeout_seconds,
                op_executable=self.host.op_executable,
            ),
            destination=self.destination,
            lock=lock,
        )


def provision_effect_inputs(
    *,
    host: ProvisionRuntimeHost,
    request: ProvisionRequest,
    selected: SelectedCredential,
    destination: str | None = None,
    recovering: bool = False,
) -> Result[EffectInputs, ManagerError]:
    """Compose a phase with metadata and a role port, never a raw credential value."""
    resolved = destination
    if resolved is None:
        issuance = resolved_runtime_issuance(host=host, request=request, bound=True)
        if isinstance(issuance, Failure):
            return Failure(issuance.failure())
        resolved = issuance.unwrap().destination
    return Success(
        EffectInputs(
            provision=ProvisionInputs(
                selected=selected,
                credential_value=None,
                destination=resolved,
                lock=target_lock(host=host, target_ref=request.target_ref),
                fence_now=host.capture_time(),
                provision_target=_ProvisioningCall(
                    host=host,
                    request=request,
                    selected=selected,
                    destination=resolved,
                    recovering=recovering,
                ),
            )
        )
    )


def cleanup_failed_start(
    *, host: ProvisionRuntimeHost, operation: OperationRecord, inputs: EffectInputs
) -> Result[None, ManagerError]:
    """Replace a definitively uncommitted start with cleanup and drive it durably."""
    engine = engine_for(host=host)
    standing = pending_operation(
        engine=engine, command="provision", idempotency_key=operation.idempotency_key
    )
    if isinstance(standing, Failure):
        return Failure(standing.failure())
    current = standing.unwrap()
    if current is None:
        return Failure(store_unavailable(message="the failed provision operation disappeared"))
    path = operation_path(
        state_dir=host.state_dir,
        command="provision",
        idempotency_key=operation.idempotency_key,
    )
    if isinstance(path, Failure):
        return Failure(path.failure())
    cleanup = transition_operation(
        path=path.unwrap(),
        operation=current,
        condition="pre-commit-failure",
        context=PlanContext(prepared_state_exists=True),
        terminal_result=None,
        owner_uid=host.owner_uid,
    )
    if isinstance(cleanup, Failure):
        return Failure(cleanup.failure())
    cleanup_operation = cleanup.unwrap()
    if cleanup_operation is None:
        return Failure(store_unavailable(message="provision cleanup was not installed"))
    return finish_provision_cleanup(
        host=host, operation=cleanup_operation, inputs=inputs, prepared=True
    )


def finish_provision_cleanup(
    *,
    host: ProvisionRuntimeHost,
    operation: OperationRecord,
    inputs: EffectInputs,
    prepared: bool,
) -> Result[None, ManagerError]:
    """Drive retained cleanup through assignment discard and lease release."""
    driven = drive_operation(
        engine=engine_for(host=host),
        operation=operation,
        inputs=inputs,
        condition="every-effect-committed",
        context=PlanContext(prepared_state_exists=prepared),
        terminal_result=None,
    )
    if isinstance(driven, Failure):
        return Failure(driven.failure())
    return Success(None)
