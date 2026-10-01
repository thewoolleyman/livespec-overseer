"""The ten-member write-ahead operation record and its positional effect identity.

SPECIFICATION/contracts.md states the write-ahead operation record as containing EXACTLY
`version`, `operation_id`, `command`, `phase`, `idempotency_key`, `accepted_at`,
`normalized_input`, `terminal_result`, `ordered_effects` and `completed_step` — ten
members, no more and no fewer — and closes both the nine-command vocabulary and the phases
each command may stand in.

TEN IS NOT A ROUNDING. A five-field substitute was explicitly refused for this engine,
because each of the last four members carries a distinct recovery decision: `accepted_at`
fixes every tombstone time a retry may later write, `normalized_input` is what a resuming
command replays from, `terminal_result` is what makes a worker's outcome durable before the
worker is gone, and the `ordered_effects`/`completed_step` pair is the only thing that can
say which effects of an interrupted phase already committed.

EFFECT IDENTITY IS POSITIONAL, NOT NAME-BASED, and that is the property the whole replay
rests on. Repeated effect names are permitted — an acquire `terminal` phase appends to the
audit log TWICE — so a name cannot identify a position. The contract therefore derives each
position's `effect_id` from `LP(operation_id) || LP(command) || LP(idempotency_key) ||
LP(phase) || LP(base10-index)`, which makes index 1 and index 3 of that phase two different
effects even though both are `audit-append`, and makes every effect of a REPLACED phase
distinct from every effect of the phase it replaced. The identifier is DERIVED rather than
stored: adding it to the record would make it an eleventh member and let a stored value
disagree with its own position.

`completed_step` RUNS FROM -1, not from 0. The unstarted value has to be representable
separately from "position 0 is done", because the one crash window this engine exists to
survive is exactly the gap between an effect committing and its checkpoint advancing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import is_sha256_hex
from _lpm_operation_terminal import terminal_result_defect
from _lpm_record import is_uuid4
from _lpm_results import ManagerError, store_unavailable
from _lpm_time import is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "EFFECT_NAMES",
    "IDEMPOTENCY_FIELDS",
    "OPERATION_COMMANDS",
    "OPERATION_MEMBERS",
    "OPERATION_VERSION",
    "PHASES_BY_COMMAND",
    "UNSTARTED_STEP",
    "WORKER_COMMANDS",
    "OperationRecord",
    "operation_from_object",
    "operation_object",
]

OPERATION_VERSION: Final = 1
UNSTARTED_STEP: Final = -1

OPERATION_MEMBERS: Final = (
    "version",
    "operation_id",
    "command",
    "phase",
    "idempotency_key",
    "accepted_at",
    "normalized_input",
    "terminal_result",
    "ordered_effects",
    "completed_step",
)

WORKER_COMMANDS: Final = ("acquire", "reacquire", "revalidate")

PHASES_BY_COMMAND: Final[dict[str, tuple[str, ...]]] = {
    "acquire": ("launch", "terminal", "recovery"),
    "reacquire": ("launch", "terminal", "recovery"),
    "revalidate": ("launch", "terminal", "recovery"),
    "target": ("issue",),
    "provision": ("start", "cleanup", "postcommit"),
    "report": ("apply",),
    "complete": ("apply",),
    "release": ("apply",),
    "expire": ("close",),
}
OPERATION_COMMANDS: Final = tuple(PHASES_BY_COMMAND)

EFFECT_NAMES: Final = (
    "worker-record-create",
    "audit-append",
    "secret-value-set",
    "credential-conditional-set",
    "worker-record-remove",
    "registration-remove",
    "issuance-create",
    "lease-create",
    "prepared-assignment-create",
    "target-write",
    "assignment-commit",
    "prepared-assignment-discard",
    "selection-update",
    "proof-update",
    "report-marker-update",
    "completion-update",
    "assignment-end-update",
    "lease-release",
    "tombstone-create",
    "assignment-close",
)

IDEMPOTENCY_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "acquire": ("provider", "account_id", "kind", "purpose"),
    "reacquire": ("record_id",),
    "revalidate": ("record_id",),
    "target": ("consumer_run_id",),
    "provision": ("consumer_run_id",),
    "report": ("consumer_run_id", "record_id", "occurred_at", "classification"),
    "complete": ("consumer_run_id", "record_id"),
    "release": ("consumer_run_id", "record_id"),
    "expire": ("consumer_run_id", "record_id"),
}


@dataclass(frozen=True, kw_only=True)
class OperationRecord:
    """One secret-free write-ahead operation record. Nine members plus the fixed version."""

    operation_id: str
    command: str
    phase: str
    idempotency_key: str
    accepted_at: str
    normalized_input: dict[str, object]
    terminal_result: dict[str, object] | None
    ordered_effects: tuple[str, ...]
    completed_step: int


def operation_object(*, operation: OperationRecord) -> dict[str, object]:
    """The exact ten-member mapping for `operation`.

    `ordered_effects` is re-listed rather than handed over as the stored tuple, so the
    canonical encoder receives a JSON array and no caller can mutate a record's plan
    through a shared sequence.
    """
    values: dict[str, object] = {"version": OPERATION_VERSION}
    for member in OPERATION_MEMBERS[1:]:
        values[member] = getattr(operation, member)
    values["ordered_effects"] = list(operation.ordered_effects)
    return values


def operation_from_object(*, parsed: object) -> Result[OperationRecord, ManagerError]:
    """Validate one decoded operation record against every invariant this layer owns.

    A defect is `store-unavailable` rather than an ineligibility: unlike a credential
    record, there is no second operation record that could satisfy the same command, and
    the contract requires a malformed manager-local file to fail closed without reset or
    mutation.
    """
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="operation record must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    membership = _membership_defect(source=source)
    if membership is not None:
        return Failure(store_unavailable(message=membership))
    identity = _identity_defect(source=source)
    if identity is not None:
        return Failure(store_unavailable(message=identity))
    effects = _effects_defect(source=source)
    if effects is not None:
        return Failure(store_unavailable(message=effects))
    command = str(source["command"])
    phase = str(source["phase"])
    terminal = terminal_result_defect(
        command=command, phase=phase, terminal_result=source["terminal_result"]
    )
    if terminal is not None:
        return Failure(store_unavailable(message=terminal))
    return Success(
        OperationRecord(
            operation_id=str(source["operation_id"]),
            command=command,
            phase=phase,
            idempotency_key=str(source["idempotency_key"]),
            accepted_at=str(source["accepted_at"]),
            normalized_input=cast("dict[str, object]", source["normalized_input"]),
            terminal_result=cast("dict[str, object] | None", source["terminal_result"]),
            ordered_effects=tuple(cast("list[str]", source["ordered_effects"])),
            completed_step=cast("int", source["completed_step"]),
        )
    )


def _membership_defect(*, source: dict[str, object]) -> str | None:
    missing = [member for member in OPERATION_MEMBERS if member not in source]
    if missing:
        return f"operation record is missing {missing[0]}"
    extra = sorted(set(source) - set(OPERATION_MEMBERS))
    if extra:
        return f"operation record has extra member {extra[0]}"
    version = source["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != OPERATION_VERSION:
        return "operation record version must be the integer 1"
    return None


def _identity_defect(*, source: dict[str, object]) -> str | None:
    operation_id = source["operation_id"]
    if not isinstance(operation_id, str) or not is_uuid4(value=operation_id):
        return "operation_id must be a lowercase RFC 4122 UUIDv4"
    command = source["command"]
    if not isinstance(command, str) or command not in PHASES_BY_COMMAND:
        return "command must be one ratified operation command"
    if source["phase"] not in PHASES_BY_COMMAND[command]:
        return f"phase must be one of {', '.join(PHASES_BY_COMMAND[command])} for {command}"
    return _input_defect(source=source)


def _input_defect(*, source: dict[str, object]) -> str | None:
    key = source["idempotency_key"]
    if not isinstance(key, str) or not is_sha256_hex(value=key):
        return "idempotency_key must be a lowercase SHA-256 hex digest"
    accepted_at = source["accepted_at"]
    if not isinstance(accepted_at, str) or not is_canonical_timestamp(text=accepted_at):
        return "accepted_at must be a UTC RFC 3339-second timestamp"
    if not isinstance(source["normalized_input"], dict):
        return "normalized_input must be a JSON object"
    return None


def _effects_defect(*, source: dict[str, object]) -> str | None:
    effects = source["ordered_effects"]
    if not isinstance(effects, list) or effects == []:
        return "ordered_effects must be a non-empty array"
    for entry in cast("list[object]", effects):
        if entry not in EFFECT_NAMES:
            return "ordered_effects must name only ratified effects"
    step = source["completed_step"]
    if isinstance(step, bool) or not isinstance(step, int):
        return "completed_step must be an integer"
    if step < UNSTARTED_STEP or step >= len(cast("list[object]", effects)):
        return "completed_step must run from -1 through the last effect index"
    return None
