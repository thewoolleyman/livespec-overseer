"""Compose durable operation replay into the installed command runtime."""

from __future__ import annotations

from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine import drive_operation, pending_operation, resume_phase
from _lpm_engine_context import EffectInputs, OperationEngine
from _lpm_operation import OperationRecord
from _lpm_operation_plan import PlanContext
from _lpm_operation_replay import ReplayProgress
from _lpm_operation_store import operation_path, transition_operation
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Failure, Result

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "recover_provision_phase",
    "recover_target_phase",
]


def recover_target_phase(
    *, engine: OperationEngine, idempotency_key: str, inputs: EffectInputs
) -> Result[OperationRecord | None, ManagerError]:
    """Replay the durable target phase, then remove its completed operation record."""
    replay = resume_phase(
        engine=engine,
        command="target",
        idempotency_key=idempotency_key,
        inputs=inputs,
    ).unwrap()
    return _finish_replayed_target(engine=engine, replay=replay)


def recover_provision_phase(
    *, engine: OperationEngine, idempotency_key: str, inputs: EffectInputs
) -> Result[OperationRecord | None, ManagerError]:
    """Replay a refused provision start, clean its preparation, and retain its refusal."""
    refusal = resume_phase(
        engine=engine,
        command="provision",
        idempotency_key=idempotency_key,
        inputs=inputs,
    ).failure()
    standing = cast(
        "OperationRecord",
        pending_operation(
            engine=engine,
            command="provision",
            idempotency_key=idempotency_key,
        ).unwrap(),
    )
    path = operation_path(
        state_dir=engine.state_dir,
        command=standing.command,
        idempotency_key=standing.idempotency_key,
    ).unwrap()
    cleanup = cast(
        "OperationRecord",
        transition_operation(
            path=path,
            operation=standing,
            condition="pre-commit-failure",
            context=PlanContext(prepared_state_exists=True),
            terminal_result=None,
            owner_uid=engine.owner_uid,
        ).unwrap(),
    )
    _ = drive_operation(
        engine=engine,
        operation=cleanup,
        inputs=inputs,
        condition="every-effect-committed",
        context=PlanContext(prepared_state_exists=True),
        terminal_result=None,
    ).unwrap()
    return Failure(refusal)


def _finish_replayed_target(
    *, engine: OperationEngine, replay: ReplayProgress
) -> Result[OperationRecord | None, ManagerError]:
    record = replay.operation
    return transition_operation(
        path=operation_path(
            state_dir=engine.state_dir,
            command=record.command,
            idempotency_key=record.idempotency_key,
        ).unwrap(),
        operation=record,
        condition="every-effect-committed",
        context=PlanContext(),
        terminal_result=None,
        owner_uid=engine.owner_uid,
    )
