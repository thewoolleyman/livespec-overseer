"""Final-provisioning and authoritative-status work performed inside target roles."""

from __future__ import annotations

import datetime
import fcntl
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from _lpm_localstate import read_local_record
from _lpm_op_entrypoints import provisioning_result
from _lpm_op_values import ValueReference, commit_status_result
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, store_unavailable
from _lpm_role_context import RoleContext, role_context, role_entry
from _lpm_runtime_base import target_lock_path
from _lpm_target import CommitOutcome, TargetIssuance, issuance_from_object, resolve_issuance
from _lpm_target_evidence import (
    TargetEvidenceBinding,
    commit_with_evidence,
    target_status_with_evidence,
)
from _lpm_time import capture_manager_time

from overseer._vendor.returns.result import Failure, Result, Success, safe

__all__: list[str] = [
    "target_role_result",
]


@dataclass(frozen=True, kw_only=True)
class _TargetWrite:
    binding: TargetEvidenceBinding
    lease_expires_at: str

    def __call__(self, *, value: bytes) -> CommitOutcome:
        return commit_with_evidence(
            binding=self.binding,
            value=value,
            lease_expires_at=self.lease_expires_at,
            sample_time=_manager_now,
        )


def target_role_result(
    *,
    role_name: str,
    members: dict[str, object],
    environ: Mapping[str, str],
    lock_descriptor: int | None,
) -> dict[str, object]:
    """Execute final provisioning or status under the inherited reference lock."""
    return (
        role_context()
        .map(
            lambda context: _target_result(
                context=context,
                role_name=role_name,
                members=members,
                environ=environ,
                lock_descriptor=lock_descriptor,
            )
        )
        .value_or(_failure())
    )


def _target_result(
    *,
    context: RoleContext,
    role_name: str,
    members: dict[str, object],
    environ: Mapping[str, str],
    lock_descriptor: int | None,
) -> dict[str, object]:
    issuance = _locked_issuance(
        context=context,
        members=members,
        lock_descriptor=lock_descriptor,
    )
    if issuance is None:
        return _failure()
    if role_name == "final-provisioning":
        return _provision(
            context=context,
            issuance=issuance,
            members=members,
            environ=environ,
        )
    status = target_status_with_evidence(
        binding=_evidence_binding(context=context, issuance=issuance, members=members)
    )
    return status.map(lambda outcome: commit_status_result(outcome=outcome)).value_or(_failure())


def _provision(
    *,
    context: RoleContext,
    issuance: TargetIssuance,
    members: dict[str, object],
    environ: Mapping[str, str],
) -> dict[str, object]:
    resolved = resolve_issuance(
        issuance=issuance,
        target_ref=cast("str", members["target_ref"]),
        consumer_run_id=cast("str", members["consumer_run_id"]),
        now=issuance.issued_at,
        bound=True,
    )

    def binding() -> str | None:
        return resolved.map(lambda _destination: None).value_or("target binding unavailable")

    return provisioning_result(
        entry=role_entry(
            role_name="final-provisioning",
            members=members,
            environ=environ,
            context=context,
        ),
        reference=ValueReference(
            record_id=cast("str", members["record_id"]),
            value_generation=cast("str", members["value_generation"]),
            value_ref=cast("str", members["value_ref"]),
        ),
        binding=binding,
        write=_TargetWrite(
            binding=_evidence_binding(context=context, issuance=issuance, members=members),
            lease_expires_at=cast("str", members["lease_expires_at"]),
        ),
    )


def _locked_issuance(
    *, context: RoleContext, members: dict[str, object], lock_descriptor: int | None
) -> TargetIssuance | None:
    path = local_record_path(
        state_dir=context.state_dir,
        family="issuance",
        identity=(cast("str", members["target_ref"]),),
    ).unwrap()
    stored = read_local_record(path=path, owner_uid=context.owner_uid).unwrap()
    return (
        issuance_from_object(parsed=stored)
        .map(
            lambda issuance: _locked(
                context=context, issuance=issuance, descriptor=lock_descriptor
            ).value_or(None)
        )
        .value_or(None)
    )


def _locked(
    *, context: RoleContext, issuance: TargetIssuance, descriptor: int | None
) -> Result[TargetIssuance, ManagerError]:
    if not _valid_lock(context=context, issuance=issuance, descriptor=descriptor):
        return Failure(store_unavailable(message="the inherited target lock is invalid"))
    return Success(issuance)


def _valid_lock(*, context: RoleContext, issuance: TargetIssuance, descriptor: int | None) -> bool:
    if descriptor is None:
        return False
    expected = target_lock_path(state_dir=context.state_dir, target_ref=issuance.reference)
    return _locked_path_matches(descriptor=descriptor, expected=expected).value_or(
        default_value=False
    )


@safe(exceptions=(OSError,))
def _locked_path_matches(*, descriptor: int, expected: Path) -> bool:
    actual = Path(f"/proc/self/fd/{descriptor}").resolve(strict=True)
    expected_path = expected.resolve(strict=True)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return actual == expected_path


def _evidence_binding(
    *, context: RoleContext, issuance: TargetIssuance, members: Mapping[str, object]
) -> TargetEvidenceBinding:
    return TargetEvidenceBinding(
        state_dir=context.state_dir,
        destination=issuance.destination,
        owner_uid=context.owner_uid,
        target_ref=issuance.reference,
        consumer_run_id=issuance.consumer_run_id,
        value_generation=cast("str", members["value_generation"]),
    )


def _manager_now() -> str:
    return capture_manager_time(now=datetime.datetime.now(tz=datetime.timezone.utc))


def _failure() -> dict[str, object]:
    return {"version": 1, "status": "store-unavailable"}
