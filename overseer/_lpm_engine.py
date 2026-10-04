"""The durable-operation engine: drive one phase, then take its ratified transition.

SPECIFICATION/contracts.md requires a command to persist its write-ahead operation record
BEFORE applying effects, to perform each ordered position only after inspecting that
position's authoritative postcondition, to checkpoint `completed_step` positionally, and —
once every effect in the phase commits and the transition condition is known — to atomically
replace the record with its contract-defined next phase and that phase's complete effect
array while resetting `completed_step` to `-1`. This module is that composition and nothing
else: it owns no effect, no plan table and no transition table.

THIS IS THE PRODUCTION PATH, AND IT IS THE SAME ONE A CRASH REPLAYS THROUGH. `drive_phase`
builds the real executor from the one real effect registry and the real checkpoint writer
from the real deterministic operation path, so there is no second algorithm for recovery to
take. `resume_phase` differs only in where the record comes from — it reads the durable one
off disk rather than being handed it — which is exactly the difference a crash makes, and the
only difference it makes.

THE CHECKPOINT WRITER IS THE REAL ONE, SO ITS FAILURE IS THE REAL CRASH WINDOW. When the
record cannot be advanced after its effect committed, `drive_phase` returns that refusal with
the durable record one position BEHIND the world. That is not an untidy outcome to be papered
over; it is precisely the state the contract's postcondition inspection exists to survive,
and the next `resume_phase` settles that position rather than repeating it.

THE CALLER NAMES A CONDITION, NEVER A PHASE. `drive_operation` passes the condition straight
through to `transition_operation`, which consults the contract's own transition table; there
is no parameter here by which a caller could install a phase the contract does not reach from
the current one, or an effect array it does not state for the phase that follows.
"""

from __future__ import annotations

from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_effect_registry import execute_effect
from _lpm_engine_context import EffectContext, EffectInputs, OperationEngine
from _lpm_operation import OperationRecord
from _lpm_operation_identity import EffectPosition
from _lpm_operation_plan import PlanContext
from _lpm_operation_replay import ReplayProgress, replay_phase
from _lpm_operation_store import (
    checkpoint_step,
    operation_path,
    read_operation,
    transition_operation,
)
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "drive_operation",
    "drive_phase",
    "pending_operation",
    "resume_phase",
]


def drive_phase(
    *, engine: OperationEngine, operation: OperationRecord, inputs: EffectInputs
) -> Result[ReplayProgress, ManagerError]:
    """Perform every pending position of `operation`'s current phase, checkpointing each.

    Each executor is built from the SAME record the phase was entered on. An effect's
    identity derives from `operation_id`, `command`, `idempotency_key`, `phase` and the
    position index, none of which a checkpoint changes — so a mid-phase advance cannot shift
    the identifier of a position that has not run yet, which is what keeps a fence or an
    audit line written before a crash recognizable to the pass that follows it.
    """
    record = _record_path(engine=engine, operation=operation)
    return replay_phase(
        operation=operation,
        # `replay_phase` calls both of these POSITIONALLY, which its own published callable
        # types fix, so they are supplied as lambdas rather than as nested definitions
        # carrying positional parameters of their own.
        execute=lambda position: _performed(
            engine=engine, operation=operation, inputs=inputs, position=position
        ),
        checkpoint=lambda current, step: checkpoint_step(
            path=record, operation=current, step=step, owner_uid=engine.owner_uid
        ),
    )


def resume_phase(
    *, engine: OperationEngine, command: str, idempotency_key: str, inputs: EffectInputs
) -> Result[ReplayProgress, ManagerError]:
    """Drive whatever phase the DURABLE record for `command`/`idempotency_key` now stands at.

    An ABSENT record is `store-unavailable` rather than a quiet success: absence MEANS there
    is no pending operation, so resuming one would apply a phase nobody persisted. A caller
    asking whether one is pending asks `pending_operation` instead.
    """
    stored = pending_operation(engine=engine, command=command, idempotency_key=idempotency_key)
    if isinstance(stored, Failure):
        return stored
    record = stored.unwrap()
    if record is None:
        return Failure(store_unavailable(message=f"no pending {command} operation to resume"))
    return drive_phase(engine=engine, operation=record, inputs=inputs)


def drive_operation(
    *,
    engine: OperationEngine,
    operation: OperationRecord,
    inputs: EffectInputs,
    condition: str,
    context: PlanContext,
    terminal_result: dict[str, object] | None,
) -> Result[OperationRecord | None, ManagerError]:
    """Drive one phase to its last position, then take the transition `condition` names.

    `Success(None)` is the every-effect-committed ending: the record was REMOVED as terminal
    housekeeping. Any other success is the SAME operation standing in its next phase with
    that phase's complete effect array and `completed_step` back at `-1`.
    """
    driven = drive_phase(engine=engine, operation=operation, inputs=inputs)
    if isinstance(driven, Failure):
        return driven
    return transition_operation(
        path=_record_path(engine=engine, operation=operation),
        operation=driven.unwrap().operation,
        condition=condition,
        context=context,
        terminal_result=terminal_result,
        owner_uid=engine.owner_uid,
    )


def pending_operation(
    *, engine: OperationEngine, command: str, idempotency_key: str
) -> Result[OperationRecord | None, ManagerError]:
    """The durable record for `command`/`idempotency_key`, or None when none is pending."""
    return read_operation(
        path=_operation_record_path(
            engine=engine, command=command, idempotency_key=idempotency_key
        ),
        owner_uid=engine.owner_uid,
    )


def _performed(
    *,
    engine: OperationEngine,
    operation: OperationRecord,
    inputs: EffectInputs,
    position: EffectPosition,
) -> Result[str, ManagerError]:
    return execute_effect(
        context=EffectContext(engine=engine, operation=operation, inputs=inputs, position=position)
    )


def _record_path(*, engine: OperationEngine, operation: OperationRecord) -> Path:
    return _operation_record_path(
        engine=engine,
        command=operation.command,
        idempotency_key=operation.idempotency_key,
    )


def _operation_record_path(*, engine: OperationEngine, command: str, idempotency_key: str) -> Path:
    # The `operation` family and its two-value identity come from the contract's own local
    # path table, so this lookup has no refusal to report; an unwrap failure would be a
    # defect in that table rather than an operator-visible condition.
    return operation_path(
        state_dir=engine.state_dir, command=command, idempotency_key=idempotency_key
    ).unwrap()
