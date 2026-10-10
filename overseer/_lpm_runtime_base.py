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
from _lpm_store import SecretStore

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "RuntimeHost",
    "engine_for",
    "new_operation",
    "run_lock",
    "target_destination",
    "write_new_operation",
]


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
    def op_executable(self) -> str: ...

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
    digest = length_prefixed_digest(values=(consumer_run_id,))
    return take_lock(
        path=host.state_dir / "locks" / "run" / f"{digest}.lock",
        owner_uid=host.owner_uid,
        timeout_seconds=float(host.config.external_call_timeout_seconds),
        monotonic=host.monotonic,
        sleep=host.sleep,
    )


def target_destination(*, state_dir: Path, reference: str) -> Path:
    """Derive this runtime's isolated destination from its opaque reference."""
    digest = length_prefixed_digest(values=(reference,))
    return state_dir / "targets" / digest / "credential"
