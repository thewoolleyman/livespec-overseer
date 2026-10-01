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

from collections.abc import Sequence
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
from _lpm_paths import local_record_path
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "checkpoint_step",
    "operation_path",
    "read_operation",
    "remove_operation",
    "replace_phase",
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


def replace_phase(
    *,
    path: Path,
    operation: OperationRecord,
    phase: str,
    ordered_effects: Sequence[str],
    terminal_result: dict[str, object] | None,
    owner_uid: int,
) -> Result[OperationRecord, ManagerError]:
    """Atomically rewrite `operation` into `phase` with that phase's complete plan.

    The five identity and input members are carried over verbatim and `completed_step`
    returns to `-1`, so the replacement is the SAME operation in a new phase rather than a
    new operation — which is what keeps a retry resolving the same path and what gives every
    effect of the replacement an identifier distinct from every prior attempt's.
    """
    replacement = OperationRecord(
        operation_id=operation.operation_id,
        command=operation.command,
        phase=phase,
        idempotency_key=operation.idempotency_key,
        accepted_at=operation.accepted_at,
        normalized_input=operation.normalized_input,
        terminal_result=terminal_result,
        ordered_effects=tuple(ordered_effects),
        completed_step=UNSTARTED_STEP,
    )
    return _validated_write(path=path, operation=replacement, owner_uid=owner_uid)


def remove_operation(*, path: Path, owner_uid: int) -> Result[None, ManagerError]:
    """Remove a finished operation record; an already-absent path is the committed outcome.

    Removal is terminal HOUSEKEEPING rather than an ordered effect, so it carries no
    `effect_id` and no audit line — and it is idempotent, because the crash window between
    the last checkpoint and this unlink is survived by simply doing it again.
    """
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
