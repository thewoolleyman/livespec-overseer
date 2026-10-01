"""The two derived digests that identify an operation and each of its effect positions.

SPECIFICATION/contracts.md derives each ordered-effect position's `effect_id` from
`LP(operation_id) || LP(command) || LP(idempotency_key) || LP(phase) || LP(base10-index)`,
and fixes the stored `idempotency_key` as a per-command digest over that command's identity
fields. Both are DERIVED rather than stored alongside the record: an `effect_id` member
would make the operation record eleven members wide and let a stored value disagree with its
own position, and a second spelling of the idempotency digest is how two commands end up
resolving different operation paths for the same logical request.

THE INDEX IS WHAT CARRIES THE IDENTITY, not the effect name. Repeated names are permitted,
so the audit append at index 0 and the audit append at index 2 of one acquire `terminal`
phase are DIFFERENT effects — and because `phase` is in the digest input, replacing a phase
gives every position in the replacement a fresh identifier, which is exactly what lets a
recovery-phase append coexist with the terminal-phase append it supersedes rather than being
mistaken for it by the audit log's own idempotency scan.

`base10-index` is the position's non-negative ASCII decimal spelling with no leading zero
except the value zero, which is what `str()` of a non-negative `int` produces. The bounds
check in front of it is what keeps that true: a negative index would spell a minus sign the
contract does not admit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import length_prefixed_digest
from _lpm_operation import IDEMPOTENCY_FIELDS, OperationRecord
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "EffectPosition",
    "effect_id",
    "effect_positions",
    "idempotency_key_for",
]


@dataclass(frozen=True, kw_only=True)
class EffectPosition:
    """One position of a phase's plan: its index, its effect name and its derived identity.

    The three travel together because an executor needs all three and must not re-derive the
    identity from the name — two positions can hold the SAME name, and an identity re-derived
    from a name would collide exactly where the collision is most harmful.
    """

    index: int
    effect: str
    effect_id: str


def effect_id(*, operation: OperationRecord, index: int) -> Result[str, ManagerError]:
    """The logical identifier of `operation`'s effect at `index`.

    An index outside the current phase's plan is a caller BUG rather than an
    operator-correctable condition: every executor derives its position from the stored
    array, so an out-of-range ask means the code is replaying a plan it is not holding.
    """
    if index < 0 or index >= len(operation.ordered_effects):
        return Failure(
            internal_bug(message="effect index is outside the operation's ordered effects")
        )
    return Success(_position_digest(operation=operation, index=index))


def effect_positions(*, operation: OperationRecord) -> tuple[EffectPosition, ...]:
    """Every position of `operation`'s current phase, each with its derived identity.

    Total by construction, and deliberately not on the Result rail: the indices come from the
    stored array itself, so the out-of-range case `effect_id` exists to refuse cannot arise
    here, and a refusal channel would be dead code at every call site.
    """
    return tuple(
        EffectPosition(
            index=index,
            effect=effect,
            effect_id=_position_digest(operation=operation, index=index),
        )
        for index, effect in enumerate(operation.ordered_effects)
    )


def idempotency_key_for(*, command: str, identity: Mapping[str, str]) -> Result[str, ManagerError]:
    """The stored idempotency key for `command` over its ratified identity fields.

    Only the declared fields reach the digest, in their declared order. An identity mapping
    carrying extra keys is accepted and those keys are IGNORED, because callers assemble one
    request object and ask several commands for their own keys from it.
    """
    fields = IDEMPOTENCY_FIELDS.get(command)
    if fields is None:
        return Failure(internal_bug(message=f"unregistered operation command: {command}"))
    missing = [field for field in fields if field not in identity]
    if missing:
        return Failure(internal_bug(message=f"{command} identity needs {', '.join(fields)}"))
    return Success(length_prefixed_digest(values=[identity[field] for field in fields]))


def _position_digest(*, operation: OperationRecord, index: int) -> str:
    return length_prefixed_digest(
        values=(
            operation.operation_id,
            operation.command,
            operation.idempotency_key,
            operation.phase,
            str(index),
        )
    )
