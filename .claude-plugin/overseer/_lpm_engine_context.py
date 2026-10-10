"""The authoritative environment one ordered effect is performed against.

SPECIFICATION/contracts.md requires every executor, after taking its effect's locks, to
inspect authoritative state for THAT POSITION'S exact postcondition before performing it:
an already-satisfied postcondition advances `completed_step` WITHOUT repeating the effect,
its exact predecessor permits the effect to run, and any other state follows an explicitly
defined conditional no-op or refusal. `settle` is that rule written ONCE, so no executor
can express it differently and none can advance a position it did not actually settle.

THE TEN-MEMBER OPERATION RECORD CANNOT CARRY EVERYTHING AN EFFECT NEEDS, and that is a
property of the contract rather than an omission here. `normalized_input` is the command's
EXACT validated input — an extra member is a defect — while a provisioning effect also needs
the account and credential SELECTION that ran before the operation existed, the credential
VALUE itself, and the DESTINATION the target reference resolved to. None of those may be
persisted beside the record: the selection is re-derivable, the value is a secret the record
is forbidden to hold, and the destination belongs to the target adapter. So they arrive
BESIDE the record as `EffectInputs`, and an effect reaching for one its composition did not
supply refuses with `internal-bug` rather than inventing a value.

THE INPUTS ARE GROUPED BY PHASE FAMILY, not flattened into one bag of optionals. A flat bag
makes every effect re-ask whether each field it touches is present, which multiplies the
refusal paths and lets an effect silently proceed on a half-built composition. One required
family per effect means one refusal, and the family is exactly the set of facts that phase's
caller already has in hand.

ALMOST EVERY TIME AN EFFECT NEEDS COMES FROM THE RECORD, NEVER FROM A CLOCK. `accepted_at` is
retained byte-for-byte across every retry and phase replacement, and it fixes a tombstone's
`closed_at`, a close's `normalized_close_time` and an issuance's `issued_at`. Reading a fresh
clock inside an executor would drift all three on every replay, which is precisely the
timestamp drift an idempotent command must not have.

AN AUDIT LINE'S `attempted_at` IS THE ONE EXCEPTION, AND IT IS NOT A RELAXATION OF THAT RULE.
The contract fixes it as "manager time captured for the first adapter attempt represented by
that audit line", which is a DIFFERENT instant from acceptance rather than another spelling of
it: every retry reuses `accepted_at`, so a phase that resumes hours later attempts at the
resuming clock while its acceptance stays pinned. Deriving it from `accepted_at` would date the
line at an instant when no adapter call could have occurred. It still does not get read inside
an executor — it arrives as an `AuditInputs` sample the caller took, for the reason `fence_now`
states — and it cannot drift on replay, because the append-only log's idempotency match
deliberately ignores it, so a later pass finds the existing line and preserves the time already
stored there.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_operation import OperationRecord
from _lpm_operation_identity import EffectPosition
from _lpm_operation_replay import PERFORMED, SATISFIED
from _lpm_results import ManagerError, internal_bug
from _lpm_store import SecretStore
from _lpm_target import TargetLock

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "AuditInputs",
    "CredentialInputs",
    "EffectContext",
    "EffectInputs",
    "OperationEngine",
    "ProvisionInputs",
    "SelectedCredential",
    "TargetInputs",
    "input_integer",
    "input_text",
    "required_input",
    "settle",
]

_T = TypeVar("_T")


@dataclass(frozen=True, kw_only=True)
class SelectedCredential:
    """The credential one provisioning operation's effects are bound to.

    Selection runs BEFORE the operation record exists and is re-derivable from the store, so
    none of this is persisted in the record; it is handed to the phase that needs it.
    """

    account_id: str
    record_id: str
    value_generation: str
    value_ref: str
    receipt: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class TargetInputs:
    """What a `target` `issue` phase needs: the minted reference and where it resolves.

    The reference's unguessability is the target command's to supply, exactly as
    `new_issuance` requires, so it crosses this boundary rather than being derived here.
    """

    reference: str
    adapter: str
    destination: str


@dataclass(frozen=True, kw_only=True)
class ProvisionInputs:
    """What a `provision` phase needs beyond its validated request.

    The credential VALUE is here and nowhere else. It never enters the operation record, the
    assignment, the tombstone or an audit line; it exists only long enough for `target-write`
    to place it at the destination.

    `fence_now` is the CALLER'S clock sample, taken immediately before the phase runs, which
    the adapter compares against `lease_expires_at` to abort a write whose lease has already
    lapsed. It is an input rather than a reading taken inside the executor because a replay
    must not re-sample: the instant the commit lands at is persisted by the commit itself and
    read back from there, so the sample matters exactly once.
    """

    selected: SelectedCredential
    credential_value: bytes
    destination: str
    lock: TargetLock
    fence_now: str


@dataclass(frozen=True, kw_only=True)
class CredentialInputs:
    """The complete records one fenced `credential-conditional-set` is authorized to write.

    `expected_record` is None for an expected ABSENCE, which is a meaningful value rather
    than a missing one — so this family is required as a whole and that member is not
    separately re-checked.
    """

    desired_record: dict[str, object]
    expected_record: dict[str, object] | None


@dataclass(frozen=True, kw_only=True)
class AuditInputs:
    """The manager-time sample one audited effect dates its attempt evidence from.

    `attempt_now` is the CALLER'S clock sample, taken immediately before the phase runs, which
    the contract requires the line to record as "manager time captured for the first adapter
    attempt represented by that audit line". It is an input rather than a reading taken inside
    the executor for exactly the reason `ProvisionInputs.fence_now` gives: an executor that
    sampled for itself would re-sample on every replay.

    A resumed pass legitimately hands in a LATER sample, and that is correct rather than merely
    tolerated. The append is idempotent on every member BUT this one, so a pass arriving after
    the line exists matches it and keeps the instant the first attempt recorded; the sample is
    consumed exactly once, by whichever pass actually appends.
    """

    attempt_now: str


@dataclass(frozen=True, kw_only=True)
class EffectInputs:
    """The per-family facts a phase hands its own effects; absent families are unused."""

    target: TargetInputs | None = None
    provision: ProvisionInputs | None = None
    credential: CredentialInputs | None = None
    audit: AuditInputs | None = None


@dataclass(frozen=True, kw_only=True)
class OperationEngine:
    """The three stores every effect of every operation is performed against.

    They travel as ONE value because they are a deployment fact rather than an operation
    fact: the same state directory, owner identity and secret backend serve every command
    this process drives, and threading them separately through each surface is how a caller
    ends up driving one phase against one backend and its replay against another.
    """

    state_dir: Path
    owner_uid: int
    store: SecretStore
    lock_timeout_seconds: float = 30.0
    lock_monotonic: Callable[[], float] = time.monotonic
    lock_sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True, kw_only=True)
class EffectContext:
    """One ordered position, and everything its executor may read or write.

    The position travels WITH the context because the contract keys an effect's identity,
    its fence and its audit line on the position rather than on the effect name: a phase may
    repeat a name, and two repeats are two distinct effects.
    """

    engine: OperationEngine
    operation: OperationRecord
    inputs: EffectInputs
    position: EffectPosition


def required_input(*, value: _T | None, member: str) -> Result[_T, ManagerError]:
    """`value`, or the refusal an effect owes when its composition omitted `member`.

    This is `internal-bug` rather than `invalid-request`: the operator asked for nothing
    wrong, the code composed a phase without the facts its own effect array needs.
    """
    if value is None:
        return Failure(internal_bug(message=f"this effect needs its operation's {member}"))
    return Success(value)


def input_text(*, operation: OperationRecord, member: str) -> Result[str, ManagerError]:
    """One text member of `operation`'s already-validated normalized input.

    The record was validated on the way in, so a missing or non-text member here means an
    effect was planned for a command whose input shape does not carry it.
    """
    value = operation.normalized_input.get(member)
    if not isinstance(value, str):
        return Failure(
            internal_bug(message=f"{operation.command} normalized_input carries no {member}")
        )
    return Success(value)


def input_integer(*, operation: OperationRecord, member: str) -> Result[int, ManagerError]:
    """One integer member of `operation`'s already-validated normalized input.

    A Boolean is rejected explicitly. It is an `int` subclass, so an unguarded check would
    accept `True` as a lease duration of one second — which is both a legal-looking number
    and a value no consumer asked for.
    """
    value = operation.normalized_input.get(member)
    if isinstance(value, bool) or not isinstance(value, int):
        return Failure(
            internal_bug(message=f"{operation.command} normalized_input carries no {member}")
        )
    return Success(value)


def settle(
    *, satisfied: bool, perform: Callable[[], Result[object, ManagerError]]
) -> Result[str, ManagerError]:
    """Advance an already-satisfied postcondition, or perform the effect exactly once.

    The disposition is the EXECUTOR'S answer about authoritative state, which is why this
    takes the already-decided `satisfied` fact rather than a predicate it would evaluate
    itself: only the caller holds the locks and knows what that position's postcondition is.
    """
    if satisfied:
        return Success(SATISFIED)
    performed = perform()
    if isinstance(performed, Failure):
        return Failure(performed.failure())
    return Success(PERFORMED)
