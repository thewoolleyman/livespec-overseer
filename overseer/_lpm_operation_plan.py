"""Each phase's required ordered effects, its transitions, and its audit actor.

SPECIFICATION/contracts.md fixes the effect array of every command phase LITERALLY and
requires that "applicable effects MUST appear in this relative order". The arrays are
transcribed here once, as data, because the order is not a style choice: an `audit-append`
ordered immediately before a provisionable-token effect MUST append exactly when that
paired effect will invoke its adapter, a tombstone MUST commit before its assignment is
removed, and `lease-release` MUST be last in `cleanup` so a crash can never strand a lease
behind a discarded assignment.

THREE ARRAYS DEPEND ON AUTHORITATIVE STATE RATHER THAN ON THE COMMAND ALONE, and that is
why this is a function and not a lookup. Provision `cleanup` contains
`prepared-assignment-discard` only when prepared state exists, while report and complete
`apply` carry their full eight- and six-effect arrays against a LIVE assignment and only
their leading prefix against a TOMBSTONE. The contract states those prefixes as "exactly
the first four" and "exactly the first two", so they are sliced from the live array here
rather than written out twice — a second spelling is how a prefix drifts from its parent.

A PHASE TRANSITION IS KEYED ON A NAMED CONDITION, never inferred. The contract allows a
`launch` to become `terminal` when its worker persisted an outcome and `recovery` when the
worker was lost, and a provision `start` to become `postcommit` after a committed target and
`cleanup` after a pre-commit failure. Those are different facts about the world, so the
caller names which one it established; a table that guessed from the phase alone could
rewrite a lost worker's operation into terminal success.

THE ACTOR IS A PROPERTY OF THE PHASE, NOT OF THE PROCESS THAT RESUMES IT. The contract's
actor table identifies the SEMANTIC owner of each audited effect "even when another process
resumes its operation", and a pending metadata-effect fence's `writer_role` MUST equal that
same value. Deriving both from one function is what keeps a recovered fence replay
attributable to the actor that originally owned it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_results import ManagerError, internal_bug

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ACQUISITION_WRITER",
    "LIFECYCLE_WRITER",
    "PHASE_TRANSITIONS",
    "RECOVERY_WRITER",
    "REPORT_WRITER",
    "TRANSITION_CONDITIONS",
    "WRITER_ROLES",
    "PlanContext",
    "next_phase",
    "ordered_effects_for",
    "writer_role_for",
]

ACQUISITION_WRITER: Final = "acquisition-writer"
LIFECYCLE_WRITER: Final = "lifecycle-writer"
REPORT_WRITER: Final = "report-writer"
RECOVERY_WRITER: Final = "recovery-writer"
WRITER_ROLES: Final = (ACQUISITION_WRITER, LIFECYCLE_WRITER, REPORT_WRITER, RECOVERY_WRITER)

_WORKER_LAUNCH: Final = ("worker-record-create", "audit-append", "credential-conditional-set")
_ACQUIRE_TERMINAL: Final = (
    "audit-append",
    "secret-value-set",
    "audit-append",
    "credential-conditional-set",
    "worker-record-remove",
)
_REVALIDATE_TERMINAL: Final = ("audit-append", "credential-conditional-set", "worker-record-remove")
_WORKER_RECOVERY: Final = ("audit-append", "credential-conditional-set", "worker-record-remove")

_REPORT_APPLY: Final = (
    "audit-append",
    "credential-conditional-set",
    "proof-update",
    "report-marker-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)
_COMPLETE_APPLY: Final = (
    "proof-update",
    "completion-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)
_CLOSE_APPLY: Final = (
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)

_REPORT_TOMBSTONE_EFFECTS: Final = 4
_COMPLETE_TOMBSTONE_EFFECTS: Final = 2

TRANSITION_CONDITIONS: Final = (
    "worker-terminal",
    "worker-lost",
    "terminal-success-rewrite",
    "target-committed",
    "pre-commit-failure",
    "every-effect-committed",
)

PHASE_TRANSITIONS: Final[dict[tuple[str, str], str | None]] = {
    ("launch", "worker-terminal"): "terminal",
    ("launch", "worker-lost"): "recovery",
    ("terminal", "terminal-success-rewrite"): "recovery",
    ("terminal", "every-effect-committed"): None,
    ("recovery", "every-effect-committed"): None,
    ("start", "target-committed"): "postcommit",
    ("start", "pre-commit-failure"): "cleanup",
    ("postcommit", "every-effect-committed"): None,
    ("cleanup", "every-effect-committed"): None,
    ("issue", "every-effect-committed"): None,
    ("apply", "every-effect-committed"): None,
    ("close", "every-effect-committed"): None,
}


@dataclass(frozen=True, kw_only=True)
class PlanContext:
    """The authoritative facts that select one phase's effect array.

    Both default to the value that makes the array its SHORTEST, so a caller that has not
    yet established a fact cannot accidentally plan an effect the contract does not
    authorize for that state.
    """

    against_tombstone: bool = False
    prepared_state_exists: bool = False


def ordered_effects_for(
    *, command: str, phase: str, context: PlanContext
) -> Result[tuple[str, ...], ManagerError]:
    """The exact ordered effects `command`'s `phase` must contain under `context`."""
    if command in ("acquire", "reacquire", "revalidate"):
        return _worker_effects(command=command, phase=phase)
    if command == "target":
        return _single(
            phase=phase, expected="issue", effects=("issuance-create", "registration-remove")
        )
    if command == "provision":
        return _provision_effects(phase=phase, context=context)
    if command == "expire":
        return _single(phase=phase, expected="close", effects=_CLOSE_APPLY)
    return _apply_effects(command=command, phase=phase, context=context)


def next_phase(*, phase: str, condition: str) -> Result[str | None, ManagerError]:
    """The phase `phase` becomes under `condition`, or None when the operation is finished.

    `Success(None)` is the contract's terminal housekeeping case: every ordered effect
    committed, so the record is REMOVED rather than rewritten to another phase.
    """
    if (phase, condition) not in PHASE_TRANSITIONS:
        return Failure(
            internal_bug(message=f"no ratified transition from {phase} under {condition}")
        )
    return Success(PHASE_TRANSITIONS[(phase, condition)])


def writer_role_for(
    *, command: str, phase: str, effect: str, outcome: str | None
) -> Result[str, ManagerError]:
    """The semantic audit actor that owns `command`'s `effect` in `phase`.

    `outcome` is the stored terminal result's outcome, needed only to separate a terminal
    SUCCESS publish (`acquisition-writer`) from a terminal FAILURE lifecycle transition
    (`lifecycle-writer`) on the same effect name.
    """
    if effect not in ("audit-append", "secret-value-set", "credential-conditional-set"):
        return Failure(internal_bug(message=f"{effect} is not an audited effect"))
    if phase == "recovery":
        return Success(RECOVERY_WRITER)
    if command == "report":
        return Success(REPORT_WRITER)
    if phase == "launch":
        return Success(ACQUISITION_WRITER if command == "acquire" else LIFECYCLE_WRITER)
    if phase != "terminal":
        return Failure(internal_bug(message=f"{command} {phase} audits no credential effect"))
    return _terminal_writer(command=command, effect=effect, outcome=outcome)


def _terminal_writer(
    *, command: str, effect: str, outcome: str | None
) -> Result[str, ManagerError]:
    if effect == "secret-value-set":
        return Success(ACQUISITION_WRITER)
    if command == "revalidate":
        return Success(LIFECYCLE_WRITER)
    return Success(ACQUISITION_WRITER if outcome == "success" else LIFECYCLE_WRITER)


def _worker_effects(*, command: str, phase: str) -> Result[tuple[str, ...], ManagerError]:
    if phase == "launch":
        return Success(_WORKER_LAUNCH)
    if phase == "recovery":
        return Success(_WORKER_RECOVERY)
    if phase == "terminal":
        return Success(_REVALIDATE_TERMINAL if command == "revalidate" else _ACQUIRE_TERMINAL)
    return Failure(internal_bug(message=f"{command} has no {phase} phase"))


def _provision_effects(
    *, phase: str, context: PlanContext
) -> Result[tuple[str, ...], ManagerError]:
    if phase == "start":
        return Success(("lease-create", "prepared-assignment-create", "target-write"))
    if phase == "postcommit":
        return Success(("assignment-commit", "selection-update", "proof-update"))
    if phase == "cleanup":
        if context.prepared_state_exists:
            return Success(("prepared-assignment-discard", "lease-release"))
        return Success(("lease-release",))
    return Failure(internal_bug(message=f"provision has no {phase} phase"))


def _apply_effects(
    *, command: str, phase: str, context: PlanContext
) -> Result[tuple[str, ...], ManagerError]:
    if phase != "apply":
        return Failure(internal_bug(message=f"{command} has no {phase} phase"))
    if command == "report":
        return Success(
            _sliced(effects=_REPORT_APPLY, keep=_REPORT_TOMBSTONE_EFFECTS, context=context)
        )
    if command == "complete":
        return Success(
            _sliced(effects=_COMPLETE_APPLY, keep=_COMPLETE_TOMBSTONE_EFFECTS, context=context)
        )
    if command == "release":
        return Success(_CLOSE_APPLY)
    return Failure(internal_bug(message=f"unregistered operation command: {command}"))


def _sliced(*, effects: tuple[str, ...], keep: int, context: PlanContext) -> tuple[str, ...]:
    return effects[:keep] if context.against_tombstone else effects


def _single(
    *, phase: str, expected: str, effects: tuple[str, ...]
) -> Result[tuple[str, ...], ManagerError]:
    if phase != expected:
        return Failure(internal_bug(message=f"the only phase here is {expected}, not {phase}"))
    return Success(effects)
