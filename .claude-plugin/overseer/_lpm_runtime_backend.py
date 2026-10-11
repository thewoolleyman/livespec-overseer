"""Production credential-role ports used by the installed manager runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TypeVar, cast

from _lpm_config import ManagerConfig
from _lpm_locks import release_lock, take_lock, try_lock
from _lpm_prereq import RuntimePrerequisites, runtime_prerequisites
from _lpm_results import ManagerError, retryable_exhaustion, store_unavailable
from _lpm_role_child import ClosedRoleInput
from _lpm_role_results import CONDITIONAL_SET_MODE
from _lpm_role_runner import RoleLaunch, RoleOutcome, run_credential_role
from _lpm_roles import CredentialRole, PackagedCompanion, credential_role
from _lpm_runtime_roles import (
    FinalProvisioningRequest,
    TargetStatusRequest,
    run_final_provisioning,
    run_target_status,
)
from _lpm_store import ConditionalSet
from _lpm_target import IN_PROGRESS, CommitOutcome, TargetLock

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "RolePorts",
]

_Outcome = TypeVar("_Outcome")


@dataclass(kw_only=True)
class RolePorts:
    """Invocation-scoped store and final-provisioning role composition."""

    config: ManagerConfig
    owner_uid: int
    state_dir: Path
    environ: Mapping[str, str]
    launch: RoleLaunch
    python_executable: str
    packaged_companion: str
    _cached: Result[RuntimePrerequisites, ManagerError] | None = field(
        default=None, init=False, repr=False
    )

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        """Read one metadata chain through the isolated reader role."""
        return self._store_role(
            role_name="metadata-reader",
            request={"version": 1, "mode": "get", "record_id": record_id},
        )

    def metadata_list(self) -> dict[str, object]:
        """List metadata chains through the isolated reader role."""
        return self._store_role(role_name="metadata-reader", request={"version": 1, "mode": "list"})

    def credential_conditional_set(self, *, request: ConditionalSet) -> dict[str, object]:
        """Append a report transition through the isolated writer role."""
        return self._store_role(
            role_name="report-writer",
            request={
                "version": 1,
                "mode": CONDITIONAL_SET_MODE,
                "record_id": request.record_id,
                "effect_id": request.effect_id,
                "expected_record": request.expected_record,
                "desired_record": request.desired_record,
            },
        )

    def __call__(
        self, *, request: FinalProvisioningRequest, destination: str, lock: TargetLock
    ) -> Result[CommitOutcome, ManagerError]:
        """Run final provisioning while retaining the target-reference lock."""
        _ = destination
        return _with_prerequisites(
            result=self._prerequisites(),
            success=lambda prerequisites: self._provision_with(
                prerequisites=prerequisites,
                request=request,
                lock=lock,
            ),
            failure=lambda error: Failure(error),
        )

    def _provision_with(
        self,
        *,
        prerequisites: RuntimePrerequisites,
        request: FinalProvisioningRequest,
        lock: TargetLock,
    ) -> Result[CommitOutcome, ManagerError]:
        locked = take_lock(
            path=lock.path,
            owner_uid=self.owner_uid,
            timeout_seconds=lock.timeout_seconds,
            monotonic=lock.monotonic,
            sleep=lock.sleep,
        )
        if isinstance(locked, Failure):
            return Failure(locked.failure())
        held = locked.unwrap()
        try:
            outcome = run_final_provisioning(
                request=replace(request, op_executable=prerequisites.op_executable),
                companion=self._companion(),
                target_lock_descriptor=held.descriptor,
                environ=self.environ,
                launch=self.launch,
            )
        finally:
            release_lock(held=held)
        return _commit_outcome(outcome=outcome, operation="final provisioning")

    def target_status(
        self, *, request: TargetStatusRequest, destination: str, lock: TargetLock
    ) -> Result[CommitOutcome, ManagerError]:
        """Query authoritative evidence before any repeated credential read."""
        _ = destination
        locked = try_lock(
            path=lock.path,
            owner_uid=self.owner_uid,
        )
        if isinstance(locked, Failure):
            return Failure(locked.failure())
        held = locked.unwrap()
        if held is None:
            return Success(CommitOutcome(status=IN_PROGRESS, committed_at=None))
        try:
            outcome = run_target_status(
                request=request,
                companion=self._companion(),
                target_lock_descriptor=held.descriptor,
                environ=self.environ,
                timeout_seconds=float(self.config.external_call_timeout_seconds),
                launch=self.launch,
            )
        finally:
            release_lock(held=held)
        return _commit_outcome(outcome=outcome, operation="target status")

    def _store_role(self, *, role_name: str, request: dict[str, object]) -> dict[str, object]:
        return _with_prerequisites(
            result=self._prerequisites(),
            success=lambda prerequisites: self._store_role_with(
                prerequisites=prerequisites,
                role_name=role_name,
                request=request,
            ),
            failure=lambda _error: {"version": 1, "status": "unavailable"},
        )

    def _store_role_with(
        self,
        *,
        prerequisites: RuntimePrerequisites,
        role_name: str,
        request: dict[str, object],
    ) -> dict[str, object]:
        role = credential_role(name=role_name)
        complete = {**request, "op_executable": prerequisites.op_executable}
        outcome = run_credential_role(
            role_input=_closed_input(role=role),
            companion=self._companion(),
            role_request=complete,
            environ=self.environ,
            timeout_seconds=float(self.config.external_call_timeout_seconds),
            launch=self.launch,
        )
        return outcome.result_object

    def _prerequisites(self) -> Result[RuntimePrerequisites, ManagerError]:
        if self._cached is None:
            entries = tuple(Path(item) for item in self.environ.get("PATH", "").split(":") if item)
            self._cached = runtime_prerequisites(
                root=Path("/"), search_path=entries, executable_name="op"
            )
        return self._cached

    def _companion(self) -> PackagedCompanion:
        return PackagedCompanion(
            python_executable=self.python_executable,
            packaged_companion=self.packaged_companion,
        )


def _with_prerequisites(
    *,
    result: Result[RuntimePrerequisites, ManagerError],
    success: Callable[[RuntimePrerequisites], _Outcome],
    failure: Callable[[ManagerError], _Outcome],
) -> _Outcome:
    if isinstance(result, Failure):
        return failure(result.failure())
    return success(result.unwrap())


def _closed_input(*, role: CredentialRole | None) -> ClosedRoleInput:
    registered = cast("CredentialRole", role)
    return ClosedRoleInput(
        role_name=registered.name,
        key_description=registered.key_description,
        descriptors=registered.descriptors,
    )


def _commit_outcome(*, outcome: RoleOutcome, operation: str) -> Result[CommitOutcome, ManagerError]:
    if outcome.refusal_reason is not None:
        if not outcome.launched:
            return Failure(store_unavailable(message=f"{operation} was refused before launch"))
        return Failure(retryable_exhaustion(message=f"{operation} has an unknown target outcome"))
    if outcome.result_object["status"] == "store-unavailable":
        return Failure(store_unavailable(message=f"{operation} was unavailable before write"))
    if outcome.result_object["status"] == IN_PROGRESS:
        return Failure(retryable_exhaustion(message=f"{operation} has an unknown target outcome"))
    return Success(
        CommitOutcome(
            status=str(outcome.result_object["status"]),
            committed_at=cast("str | None", outcome.result_object["committed_at"]),
        )
    )
