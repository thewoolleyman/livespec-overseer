"""The one table from a contract effect name to the executor that performs it.

SPECIFICATION/contracts.md closes the effect vocabulary at twenty names and requires each
ordered-effect POSITION to be performed by an executor that first inspects authoritative
state for that position's exact postcondition. This module is the lookup that turns a stored
name into that executor, and it is the only place such a mapping exists — a second table
would let one command's phase resolve a name differently from another's.

THE LOOKUP IS BY NAME WHILE THE IDENTITY IS BY POSITION, and both halves matter. `phase`
arrays legitimately REPEAT a name — acquire `terminal` carries two `audit-append` entries —
so the executor is shared while the effect id, the fence and the audit line it writes are
keyed on the position. Resolving the executor positionally would require a table per phase;
resolving the IDENTITY by name would collapse two distinct contributions into one, silently
losing the second.

THREE NAMES ARE DELIBERATELY ABSENT, AND THE REFUSAL SAYS SO. `worker-record-create`,
`worker-record-remove` and `secret-value-set` belong to the acquire/reacquire/revalidate
worker lifecycle, whose `launch`, `terminal` and `recovery` phases are a separate engine
with its own value-write-once rule and its own live-worker fencing. Registering a stub for
them would make a composition that reaches one look driven when nothing happened; naming
them explicitly makes the boundary a reported fact instead of a missing dictionary key.
"""

from __future__ import annotations

from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_effects_commit import assignment_commit, target_write
from _lpm_effects_lease import lease_release
from _lpm_effects_provision import (
    lease_create,
    prepared_assignment_create,
    prepared_assignment_discard,
)
from _lpm_effects_shared import proof_update, selection_update
from _lpm_effects_target import issuance_create, registration_remove
from _lpm_engine_context import EffectContext
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "EFFECT_EXECUTORS",
    "WORKER_LIFECYCLE_EFFECTS",
    "EffectExecutor",
    "execute_effect",
    "registered_effects",
]


class EffectExecutor(Protocol):
    """One contract effect, performed against the authoritative state its context names."""

    def __call__(self, *, context: EffectContext) -> Result[str, ManagerError]:
        """The position's disposition: `satisfied` when already so, else `performed`."""
        ...


WORKER_LIFECYCLE_EFFECTS: Final = (
    "secret-value-set",
    "worker-record-create",
    "worker-record-remove",
)

EFFECT_EXECUTORS: Final[dict[str, EffectExecutor]] = {
    "issuance-create": issuance_create,
    "registration-remove": registration_remove,
    "lease-create": lease_create,
    "prepared-assignment-create": prepared_assignment_create,
    "target-write": target_write,
    "assignment-commit": assignment_commit,
    "prepared-assignment-discard": prepared_assignment_discard,
    "selection-update": selection_update,
    "proof-update": proof_update,
    "lease-release": lease_release,
}


def registered_effects() -> tuple[str, ...]:
    """Every effect name this engine can perform, in lexical order."""
    return tuple(sorted(EFFECT_EXECUTORS))


def execute_effect(*, context: EffectContext) -> Result[str, ManagerError]:
    """Perform `context`'s position through the executor its effect name resolves to."""
    executor = EFFECT_EXECUTORS.get(context.position.effect)
    if executor is None:
        return Failure(_unregistered(effect=context.position.effect))
    return executor(context=context)


def _unregistered(*, effect: str) -> ManagerError:
    if effect in WORKER_LIFECYCLE_EFFECTS:
        return internal_bug(
            message=f"{effect} belongs to the worker-lifecycle engine, not this one"
        )
    return internal_bug(message=f"{effect} resolves to no registered effect executor")
