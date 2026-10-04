"""Validated, atomic persistence of one write-ahead operation record.

SPECIFICATION/contracts.md requires that before a command applies effects across the
provisionable-token store and manager-local state it PERSIST a secret-free write-ahead
record; that every retry, recovery and phase replacement of that record retain its
`operation_id` BYTE-FOR-BYTE and REUSE its `accepted_at`; that a phase replacement install
the next phase's complete effect array while resetting `completed_step` to `-1`; and that
the record be REMOVED only once every ordered effect has committed, as terminal housekeeping
that is not itself an effect.

EVERY WRITE IS VALIDATED BEFORE IT LANDS, and that is not belt-and-braces. The record is the
only thing a later process has to reconstruct what this one was doing, so a record that
cannot be read back is indistinguishable from no record at all — which is the one state the
write-ahead protocol exists to make impossible. A replacement therefore goes through exactly
the reader's own validator before it is staged, so an impossible phase, a plan naming an
unratified effect, or a terminal result the phase may not carry is refused while the prior
bytes are still on disk.

`accepted_at` IS NEVER RE-CAPTURED HERE. The contract makes it the manager's time taken
immediately after pre-operation validation and requires every retry to reuse it, because it
is what fixes a tombstone's `closed_at` and the `normalized_close_time` a close may later
write. A re-captured value would drift those times on every retry, which is precisely the
timestamp drift an idempotent command must not have; so this module copies the stored value
forward and offers no way to supply a new one.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record, remove_local_record, write_local_record
from _lpm_operation import (
    UNSTARTED_STEP,
    OperationRecord,
    operation_from_object,
    operation_object,
)
from _lpm_operation_plan import PlanContext, next_phase, ordered_effects_for
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "checkpoint_step",
    "finish_operation",
    "operation_path",
    "read_operation",
    "transition_operation",
    "write_operation",
]


def operation_path(
    *, state_dir: Path, command: str, idempotency_key: str
) -> Result[Path, ManagerError]:
    """The deterministic owner-only path of `command`'s operation under `idempotency_key`."""
    return local_record_path(
        state_dir=state_dir, family="operation", identity=(command, idempotency_key)
    )


def read_operation(*, path: Path, owner_uid: int) -> Result[OperationRecord | None, ManagerError]:
    """Read one operation record; absence MEANS there is no pending operation.

    Absence is a defined answer in this operation, so it is returned as `None` rather than
    collapsed into a refusal: only an EXISTING record is nonterminal and counts as pending.
    """
    stored = read_local_record(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return stored
    parsed = stored.unwrap()
    if parsed is None:
        return Success(None)
    return operation_from_object(parsed=parsed)


def write_operation(
    *, path: Path, operation: OperationRecord, owner_uid: int
) -> Result[OperationRecord, ManagerError]:
    """Atomically persist `operation` after validating it through the reader's own rules."""
    return _validated_write(path=path, operation=operation, owner_uid=owner_uid)


def checkpoint_step(
    *, path: Path, operation: OperationRecord, step: int, owner_uid: int
) -> Result[OperationRecord, ManagerError]:
    """Advance `operation`'s `completed_step` to `step`, which must be the next position.

    The successor requirement is what makes the marker meaningful. `completed_step` asserts
    that EVERY position up to it committed, so a jump would silently claim the positions it
    skipped — and those are exactly the effects a later replay would then never inspect.
    """
    if step != operation.completed_step + 1:
        return Failure(
            internal_bug(
                message=(
                    "a checkpoint must advance exactly one position from "
                    f"{operation.completed_step}"
                )
            )
        )
    advanced = replace(operation, completed_step=step)
    return _validated_write(path=path, operation=advanced, owner_uid=owner_uid)


def transition_operation(
    *,
    path: Path,
    operation: OperationRecord,
    condition: str,
    context: PlanContext,
    terminal_result: dict[str, object] | None,
    owner_uid: int,
) -> Result[OperationRecord | None, ManagerError]:
    """Apply the ratified transition `condition` names, or finish the operation.

    THE CALLER NAMES A CONDITION, NEVER A PHASE AND NEVER AN EFFECT ARRAY. That is the whole
    point of this surface: the contract's transition table decides which phase follows, and the
    plan tables decide that phase's complete effect array, so there is no public path by which a
    caller can install a phase the contract does not reach from here or a plan it does not state.
    An earlier shape took `phase` and `ordered_effects` directly and was exactly that hole.

    `Success(None)` is the every-effect-committed case: the record is REMOVED as terminal
    housekeeping rather than rewritten, and the removal goes through the same finished-plan
    precondition as `finish_operation`.

    The five identity and input members are carried over verbatim and `completed_step` returns
    to `-1`, so a replacement is the SAME operation in a new phase rather than a new operation —
    which is what keeps a retry resolving the same path and what gives every effect of the
    replacement an identifier distinct from every prior attempt's.
    """
    following = next_phase(phase=operation.phase, condition=condition)
    if isinstance(following, Failure):
        return following
    phase = following.unwrap()
    if phase is None:
        finished = finish_operation(path=path, operation=operation, owner_uid=owner_uid)
        if isinstance(finished, Failure):
            return finished
        return Success(None)
    effects = ordered_effects_for(command=operation.command, phase=phase, context=context)
    if isinstance(effects, Failure):
        return effects
    replacement = OperationRecord(
        operation_id=operation.operation_id,
        command=operation.command,
        phase=phase,
        idempotency_key=operation.idempotency_key,
        accepted_at=operation.accepted_at,
        normalized_input=operation.normalized_input,
        terminal_result=terminal_result,
        ordered_effects=effects.unwrap(),
        completed_step=UNSTARTED_STEP,
    )
    return _validated_write(path=path, operation=replacement, owner_uid=owner_uid)


def finish_operation(
    *, path: Path, operation: OperationRecord, owner_uid: int
) -> Result[None, ManagerError]:
    """Remove a FINISHED operation record; an already-absent path is the committed outcome.

    The finished-plan precondition is the half that matters. Removal is terminal housekeeping
    and is not itself an ordered effect, but the contract permits it only after EVERY ordered
    effect commits — so a record whose `completed_step` is not its last index is refused here
    rather than silently discarding the pending effects a later replay would have performed.

    Removal is idempotent, because the crash window between the last checkpoint and this unlink
    is survived by simply doing it again.
    """
    last = len(operation.ordered_effects) - 1
    if operation.completed_step != last:
        return Failure(
            internal_bug(
                message=(
                    "an operation is removable only once every ordered effect commits; "
                    f"completed_step is {operation.completed_step} of {last}"
                )
            )
        )
    return remove_local_record(path=path, owner_uid=owner_uid)


def _validated_write(
    *, path: Path, operation: OperationRecord, owner_uid: int
) -> Result[OperationRecord, ManagerError]:
    encoded = operation_object(operation=operation)
    validated = operation_from_object(parsed=encoded)
    if isinstance(validated, Failure):
        return validated
    written = write_local_record(path=path, value=encoded, owner_uid=owner_uid)
    if isinstance(written, Failure):
        return written
    return Success(validated.unwrap())
