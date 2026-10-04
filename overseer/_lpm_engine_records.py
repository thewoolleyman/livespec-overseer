"""Settling ONE manager-local record against one ordered effect's postcondition.

SPECIFICATION/contracts.md requires every executor to inspect authoritative state for its
position's exact postcondition before performing it: an already-satisfied postcondition
advances `completed_step` without repeating the effect, its exact predecessor permits the
effect to run, and any other state follows an explicitly defined conditional no-op or
refusal. Most of this operation's effects express that against exactly one local record, so
the READ, the DECISION and the WRITE are separated here and the I/O half is written once.

WHAT EACH EFFECT CONTRIBUTES IS ITS DECISION, NOTHING ELSE. `settle_record` hands the stored
content to the effect's own `decide` and does what the returned action says. That is what
keeps an executor free of filesystem branching it would otherwise have to repeat — and it is
why a defect in one effect's postcondition reasoning cannot turn into a different I/O
behaviour from its siblings'.

ABSENCE IS PASSED THROUGH AS `None`, NEVER COLLAPSED. The contract defines an absent
issuance, lease, assignment, tombstone, operation or fence to MEAN that entity does not
exist, and several effects decide differently on absence than on a mismatch — a create
proceeds, a delete is already committed, a conditional update refuses. Folding absence into
either neighbour would silently pick one of those three for all of them.

A REMOVAL AND A WRITE ARE BOTH `performed`. The disposition answers whether THIS pass did the
work, which is what the replay driver records; it does not describe the shape of the work. A
delete effect that found its record already gone reports `satisfied` instead, because the
contract defines that absence as the committed postcondition rather than as work to redo.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_engine_context import EffectContext
from _lpm_localstate import read_local_record, remove_local_record, write_local_record
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_paths import local_record_path
from _lpm_results import ManagerError

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "KEEP",
    "REMOVE",
    "WRITE",
    "RecordAction",
    "record_path",
    "remove_action",
    "satisfied_action",
    "settle_record",
    "stored_record",
    "write_action",
]

KEEP: Final = "keep"
WRITE: Final = "write"
REMOVE: Final = "remove"


@dataclass(frozen=True, kw_only=True)
class RecordAction:
    """What one effect decided its target local record needs: nothing, a value, or removal."""

    kind: str
    value: object | None = None


def satisfied_action() -> RecordAction:
    """The action for a postcondition authoritative state already holds."""
    return RecordAction(kind=KEEP)


def write_action(*, value: object) -> RecordAction:
    """The action that atomically replaces the record with `value`."""
    return RecordAction(kind=WRITE, value=value)


def remove_action() -> RecordAction:
    """The action that removes the record."""
    return RecordAction(kind=REMOVE)


def record_path(*, state_dir: Path, family: str, identity: Sequence[str]) -> Path:
    """The deterministic owner-only path of one local record in a closed contract family.

    Every call site names a family from the contract's own table with that family's declared
    identity arity, so `local_record_path`'s `internal-bug` refusal has nothing to report
    here; an unwrap failure would be a defect in this engine's own tables rather than an
    operator-visible condition, and belongs on the bug rail.
    """
    return local_record_path(state_dir=state_dir, family=family, identity=identity).unwrap()


def stored_record(
    *, context: EffectContext, family: str, identity: Sequence[str]
) -> Result[object | None, ManagerError]:
    """The current authoritative content of one local record, or None for its absence.

    An UNSAFE record — symlinked, non-regular, wrongly owned, more broadly accessible or
    malformed — is a refusal and is left exactly as found, never reset to initial state.
    """
    return read_local_record(
        path=record_path(state_dir=context.engine.state_dir, family=family, identity=identity),
        owner_uid=context.engine.owner_uid,
    )


def settle_record(
    *,
    context: EffectContext,
    family: str,
    identity: Sequence[str],
    decide: Callable[[object | None], Result[RecordAction, ManagerError]],
) -> Result[str, ManagerError]:
    """Read one local record, ask `decide` what it needs, and report the disposition."""
    stored = stored_record(context=context, family=family, identity=identity)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    action = decide(stored.unwrap())
    if isinstance(action, Failure):
        return action
    return _applied(
        path=record_path(state_dir=context.engine.state_dir, family=family, identity=identity),
        owner_uid=context.engine.owner_uid,
        action=action.unwrap(),
    )


def _applied(*, path: Path, owner_uid: int, action: RecordAction) -> Result[str, ManagerError]:
    if action.kind == KEEP:
        return Success(SATISFIED)
    performed = (
        remove_local_record(path=path, owner_uid=owner_uid)
        if action.kind == REMOVE
        else write_local_record(path=path, value=action.value, owner_uid=owner_uid)
    )
    if isinstance(performed, Failure):
        return Failure(performed.failure())
    return Success(PERFORMED)
