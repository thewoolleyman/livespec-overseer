"""Compose the manager's secret-free final-provisioning role transport."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_role_child import ClosedRoleInput
from _lpm_role_runner import RoleLaunch, RoleOutcome, run_credential_role
from _lpm_roles import CredentialRole, PackagedCompanion, credential_role

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "FinalProvisioningRequest",
    "TargetStatusRequest",
    "run_final_provisioning",
    "run_target_status",
]


@dataclass(frozen=True, kw_only=True)
class FinalProvisioningRequest:
    """The secret-free identity sent to final provisioning."""

    target_ref: str
    consumer_run_id: str
    record_id: str
    value_generation: str
    value_ref: str
    lease_expires_at: str
    external_call_timeout_seconds: int
    op_executable: str


@dataclass(frozen=True, kw_only=True)
class TargetStatusRequest:
    """The exact secret-free identity an interrupted write reconciliation receives."""

    target_ref: str
    consumer_run_id: str
    value_generation: str


def run_final_provisioning(
    *,
    request: FinalProvisioningRequest,
    companion: PackagedCompanion,
    target_lock_descriptor: int,
    environ: Mapping[str, str],
    launch: RoleLaunch,
) -> RoleOutcome:
    """Launch final provisioning without reading or carrying a credential value."""
    role = cast("CredentialRole", credential_role(name="final-provisioning"))
    return run_credential_role(
        role_input=ClosedRoleInput(
            role_name=role.name,
            key_description=role.key_description,
            descriptors=role.descriptors,
            descriptor_fds={"target-reference-lock": target_lock_descriptor},
        ),
        companion=companion,
        role_request=_request_object(request=request),
        environ=environ,
        timeout_seconds=float(request.external_call_timeout_seconds),
        launch=launch,
    )


def run_target_status(
    *,
    request: TargetStatusRequest,
    companion: PackagedCompanion,
    target_lock_descriptor: int,
    environ: Mapping[str, str],
    timeout_seconds: float,
    launch: RoleLaunch,
) -> RoleOutcome:
    """Launch the tokenless status role under the inherited reference lock."""
    role = cast("CredentialRole", credential_role(name="target-status"))
    return run_credential_role(
        role_input=ClosedRoleInput(
            role_name=role.name,
            key_description=role.key_description,
            descriptors=role.descriptors,
            descriptor_fds={"target-reference-lock": target_lock_descriptor},
        ),
        companion=companion,
        role_request={
            "version": 1,
            "target_ref": request.target_ref,
            "consumer_run_id": request.consumer_run_id,
            "value_generation": request.value_generation,
        },
        environ=environ,
        timeout_seconds=timeout_seconds,
        launch=launch,
    )


def _request_object(*, request: FinalProvisioningRequest) -> dict[str, object]:
    return {
        "version": 1,
        "target_ref": request.target_ref,
        "consumer_run_id": request.consumer_run_id,
        "record_id": request.record_id,
        "value_generation": request.value_generation,
        "value_ref": request.value_ref,
        "lease_expires_at": request.lease_expires_at,
        "external_call_timeout_seconds": request.external_call_timeout_seconds,
        "op_executable": request.op_executable,
    }
