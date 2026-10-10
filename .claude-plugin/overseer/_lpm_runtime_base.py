"""Shared host facts, locking and write-ahead operation construction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import length_prefixed_digest
from _lpm_config import ManagerConfig
from _lpm_engine_context import OperationEngine
from _lpm_localstate import ensure_state_directory
from _lpm_locks import HeldLock, take_lock
from _lpm_operation import OperationRecord
from _lpm_operation_identity import idempotency_key_for
from _lpm_operation_plan import PlanContext, ordered_effects_for
from _lpm_operation_store import operation_path, write_operation
from _lpm_results import ManagerError
from _lpm_runtime_roles import FinalProvisioningRequest, TargetStatusRequest
from _lpm_store import SecretStore
from _lpm_target import CommitOutcome, TargetLock

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "FinalProvisioningPort",
    "ProvisionRuntimeHost",
    "RuntimeHost",
    "TargetStatusPort",
    "engine_for",
    "new_operation",
    "run_lock",
    "target_destination",
    "target_lock",
    "target_lock_path",
    "write_new_operation",
]


class FinalProvisioningPort(Protocol):
    """The parent-visible, secret-free final provisioning role boundary."""

    def __call__(
        self, *, request: FinalProvisioningRequest, destination: str, lock: TargetLock
    ) -> Result[CommitOutcome, ManagerError]: ...


class TargetStatusPort(Protocol):
    """The tokenless authoritative query for one interrupted target write."""

    def __call__(
        self, *, request: TargetStatusRequest, destination: str, lock: TargetLock
    ) -> Result[CommitOutcome, ManagerError]: ...


class RuntimeHost(Protocol):
    """The validated facts shared by concrete runtime command implementations."""

    @property
    def state_dir(self) -> Path: ...

    @property
    def owner_uid(self) -> int: ...

    @property
    def config(self) -> ManagerConfig: ...

    @property
    def store(self) -> SecretStore: ...

    @property
    def op_executable(self) -> str | None: ...

    @property
    def capture_time(self) -> Callable[[], str]: ...

    @property
    def new_operation_id(self) -> Callable[[], str]: ...

    @property
    def monotonic(self) -> Callable[[], float]: ...

    @property
    def sleep(self) -> Callable[[float], None]: ...


class ProvisionRuntimeHost(Protocol):
    """Runtime facts used only by the provision command."""

    @property
    def state_dir(self) -> Path: ...

    @property
    def owner_uid(self) -> int: ...

    @property
    def config(self) -> ManagerConfig: ...

    @property
    def store(self) -> SecretStore: ...

    @property
    def provision_target(self) -> FinalProvisioningPort: ...

    @property
    def target_status(self) -> TargetStatusPort | None: ...

    @property
    def op_executable(self) -> str | None: ...

    @property
    def capture_time(self) -> Callable[[], str]: ...

    @property
    def new_operation_id(self) -> Callable[[], str]: ...

    @property
    def monotonic(self) -> Callable[[], float]: ...

    @property
    def sleep(self) -> Callable[[float], None]: ...


def engine_for(*, host: RuntimeHost) -> OperationEngine:
    """Build the one engine shared by fresh work and replay for this invocation."""
    return OperationEngine(
        state_dir=host.state_dir,
        owner_uid=host.owner_uid,
        store=host.store,
        lock_timeout_seconds=float(host.config.external_call_timeout_seconds),
        lock_monotonic=host.monotonic,
        lock_sleep=host.sleep,
    )


def new_operation(
    *,
    host: RuntimeHost,
    command: str,
    phase: str,
    normalized_input: dict[str, object],
    context: PlanContext,
) -> Result[OperationRecord, ManagerError]:
    """Build one complete operation record from validated command input."""
    identity = {name: value for name, value in normalized_input.items() if isinstance(value, str)}
    key = idempotency_key_for(command=command, identity=identity)
    if isinstance(key, Failure):
        return Failure(key.failure())
    effects = ordered_effects_for(command=command, phase=phase, context=context)
    if isinstance(effects, Failure):
        return Failure(effects.failure())
    return Success(
        OperationRecord(
            operation_id=host.new_operation_id(),
            command=command,
            phase=phase,
            idempotency_key=key.unwrap(),
            accepted_at=host.capture_time(),
            normalized_input=normalized_input,
            terminal_result=None,
            ordered_effects=effects.unwrap(),
            completed_step=-1,
        )
    )


def write_new_operation(
    *, host: RuntimeHost, operation: OperationRecord
) -> Result[OperationRecord, ManagerError]:
    """Persist a fresh operation before any of its ordered effects run."""
    path = operation_path(
        state_dir=host.state_dir,
        command=operation.command,
        idempotency_key=operation.idempotency_key,
    )
    if isinstance(path, Failure):
        return Failure(path.failure())
    return write_operation(path=path.unwrap(), operation=operation, owner_uid=host.owner_uid)


def run_lock(*, host: RuntimeHost, consumer_run_id: str) -> Result[HeldLock, ManagerError]:
    """Take the complete per-run serialization boundary for one command."""
    for path in (host.state_dir, host.state_dir / "locks", host.state_dir / "targets"):
        ensured = ensure_state_directory(path=path, owner_uid=host.owner_uid)
        if isinstance(ensured, Failure):
            return Failure(ensured.failure())
    return take_lock(
        path=_lock_path(state_dir=host.state_dir, family="run", identity=(consumer_run_id,)),
        owner_uid=host.owner_uid,
        timeout_seconds=float(host.config.external_call_timeout_seconds),
        monotonic=host.monotonic,
        sleep=host.sleep,
    )


def target_lock(*, host: RuntimeHost, target_ref: str) -> TargetLock:
    """Return the target-reference lock configuration inherited by final provisioning."""
    return TargetLock(
        path=target_lock_path(state_dir=host.state_dir, target_ref=target_ref),
        timeout_seconds=float(host.config.external_call_timeout_seconds),
        monotonic=host.monotonic,
        sleep=host.sleep,
    )


def target_lock_path(*, state_dir: Path, target_ref: str) -> Path:
    """Return the canonical target-reference lock path."""
    return _lock_path(state_dir=state_dir, family="target", identity=(target_ref,))


def target_destination(*, state_dir: Path, reference: str) -> Path:
    """Derive this runtime's isolated destination from its opaque reference."""
    digest = length_prefixed_digest(values=(reference,))
    return state_dir / "targets" / digest / "credential"


def _lock_path(*, state_dir: Path, family: str, identity: tuple[str, ...]) -> Path:
    digest = length_prefixed_digest(values=identity)
    return state_dir / "locks" / family / f"{digest}.lock"
