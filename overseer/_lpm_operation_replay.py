"""Positional replay of one phase from its authoritative effect postconditions.

SPECIFICATION/contracts.md requires that, after taking an effect's required locks, EVERY
executor inspect authoritative state for THAT POSITION'S exact postcondition before
performing it: an already-satisfied postcondition advances `completed_step` WITHOUT repeating
the effect, its exact predecessor permits the effect to run, and any other state follows an
explicitly defined conditional no-op or refusal. "These checks MUST make an effect commit
followed by a crash before `completed_step` advancement replay as one logical effect."

THAT ONE SENTENCE IS THE WHOLE REASON THIS MODULE EXISTS. The window between an effect
committing and its checkpoint landing cannot be closed — they are two different stores — so
it is survived instead. A replay re-enters at the stored checkpoint, which may be one
position BEHIND the world, and the postcondition inspection is what turns that rewind into a
no-op rather than a duplicate. Both failure directions are real and opposite: repeating a
committed `audit-append` DUPLICATES a contribution, while skipping an uncommitted one LOSES
one, and only asking authoritative state can tell those apart.

THE DISPOSITION IS THE EXECUTOR'S ANSWER, NOT THIS DRIVER'S GUESS. Only the executor holds
the locks and can read the authoritative store for its position, so it reports `satisfied` or
`performed` and this module does the bookkeeping. An unrecognized disposition is an
`internal-bug` rather than a silent advance: a driver that advanced on an answer it did not
understand would checkpoint past an effect nobody performed.

THE CHECKPOINT IS INJECTED for the same reason the executor is — and that also makes the
crash window directly expressible in a test, which is the only way this behaviour can be
exercised at all without killing a process.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_operation import OperationRecord
from _lpm_operation_identity import EffectPosition, effect_positions
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "EFFECT_DISPOSITIONS",
    "PERFORMED",
    "SATISFIED",
    "ReplayProgress",
    "pending_positions",
    "replay_phase",
]

SATISFIED: Final = "satisfied"
PERFORMED: Final = "performed"
EFFECT_DISPOSITIONS: Final = (SATISFIED, PERFORMED)

_EffectExecutor = Callable[[EffectPosition], Result[str, ManagerError]]
_Checkpoint = Callable[[OperationRecord, int], Result[OperationRecord, ManagerError]]


@dataclass(frozen=True, kw_only=True)
class ReplayProgress:
    """What one replay pass achieved, and the operation record it left behind.

    `performed` and `skipped` are kept apart deliberately. A pass that skipped a position
    found that position's postcondition ALREADY authoritative — which is the evidence that a
    prior attempt committed it and crashed before its checkpoint — and a caller or a test
    that could not see the difference could not tell a clean first pass from a successful
    recovery.
    """

    operation: OperationRecord
    performed: tuple[int, ...]
    skipped: tuple[int, ...]


def pending_positions(*, operation: OperationRecord) -> tuple[EffectPosition, ...]:
    """The positions of `operation`'s current phase at or after its stored checkpoint.

    The checkpoint is INCLUSIVE of everything before it: `completed_step` asserts that every
    earlier position committed, so the first pending position is the one just past it.
    """
    return tuple(
        position
        for position in effect_positions(operation=operation)
        if position.index > operation.completed_step
    )


def replay_phase(
    *,
    operation: OperationRecord,
    execute: _EffectExecutor,
    checkpoint: _Checkpoint,
) -> Result[ReplayProgress, ManagerError]:
    """Drive `operation`'s current phase from its stored checkpoint to its last position.

    Each position is inspected and then checkpointed before the next is attempted, so a loss
    at any point leaves the record either exactly at the last committed position or one
    behind it — never ahead of the world, which is the only direction that cannot be
    recovered from.
    """
    current = operation
    performed: list[int] = []
    skipped: list[int] = []
    for position in pending_positions(operation=operation):
        disposition = execute(position)
        if isinstance(disposition, Failure):
            return disposition
        named = disposition.unwrap()
        if named == PERFORMED:
            performed.append(position.index)
        elif named == SATISFIED:
            skipped.append(position.index)
        else:
            return Failure(internal_bug(message=f"{named} is not a ratified effect disposition"))
        advanced = checkpoint(current, position.index)
        if isinstance(advanced, Failure):
            return advanced
        current = advanced.unwrap()
    return Success(
        ReplayProgress(operation=current, performed=tuple(performed), skipped=tuple(skipped))
    )
