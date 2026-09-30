"""The manager executable's argv layer: recognize the subcommand, then its flag cardinality.

SPECIFICATION/contracts.md states the pre-recovery validation ORDER, and the first two of
its steps are settled entirely from the argument list: "recognize the subcommand; validate
that command's flag cardinality; read and validate configuration; ...". This module is
exactly those two steps and nothing after them. It reads no configuration, touches no
filesystem and performs no external access, because the contract requires a missing or
unknown subcommand to be refused "before configuration, recovery or external access" — a
property that is structural here rather than a discipline the caller must remember.

THE REFUSAL TYPE IS COMMAND-DEPENDENT, AND ONLY FOR `report`. Every command refuses a bad
flag list with `invalid-request`; a RECOGNIZED `report` refuses the equivalent failure with
`invalid-report`. Both map to exit `2`, so the distinction is invisible from the exit status
alone and has to be carried in the typed error. Recognition comes FIRST, so a misspelled
subcommand — even a `report`-shaped one — has no command-specific type to inherit and is
`invalid-request`.

NO CALLER-SUPPLIED VALUE IS EVER QUOTED INTO A MESSAGE. The manager's output is required to
be secret-free, and an argument vector is caller-controlled: a consumer that passes a
credential where a path belongs must not have it echoed back out of a refusal. Every message
below names only closed-table command and flag names.

THE ATTENTION GRAMMAR IS HERE RATHER THAN BESIDE THE OPERATOR SURFACE, because it is the
EXECUTABLE's grammar. `_lpm_operator_request` owns what a harness binding may CONSTRUCT —
the bare list vector or `acquire --acquisition-json -`, and deliberately not either attention
mutation. This module owns what the executable must ACCEPT, which is the larger set: the
local operator runs `--resolve`/`--give-up` directly against the executable, and the
contract forbids a binding from forwarding them. Two different questions, two modules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_results import ManagerError, invalid_report, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ATTENTION_ACTIONS",
    "ATTENTION_COMMAND",
    "JSON_FLAG_BY_COMMAND",
    "MANAGER_COMMANDS",
    "PROOF_STATUS_COMMAND",
    "REPORT_COMMAND",
    "ManagerInvocation",
    "manager_invocation",
]

REPORT_COMMAND: Final = "report"
ATTENTION_COMMAND: Final = "attention"
PROOF_STATUS_COMMAND: Final = "proof-status"

JSON_FLAG_BY_COMMAND: Final[dict[str, str]] = {
    "target": "--target-json",
    "provision": "--request-json",
    "report": "--report-json",
    "complete": "--completion-json",
    "release": "--release-json",
    "acquire": "--acquisition-json",
}

ATTENTION_ACTIONS: Final = ("--resolve", "--give-up")

MANAGER_COMMANDS: Final = (
    *sorted(JSON_FLAG_BY_COMMAND),
    ATTENTION_COMMAND,
    PROOF_STATUS_COMMAND,
)

_STANDARD_INPUT: Final = "-"

# Every operand-carrying shape in this grammar is exactly a flag and its one value. There is
# no command with two flags, an optional value or a bare positional, so one arity serves the
# whole table -- and naming it keeps the two cardinality checks reading as the same rule.
_FLAG_AND_VALUE: Final = 2


@dataclass(frozen=True, kw_only=True)
class ManagerInvocation:
    """One recognized invocation: the command, and whichever operand its grammar allows.

    `source` is the `<path|->` operand of a JSON-carrying command and `None` otherwise;
    `action` and `record_id` are the attention mutation operands and are `None` for every
    other shape, including the bare attention list. Keeping all three on one frozen record
    rather than in a union is what lets the dispatcher below stay a flat table lookup.
    """

    command: str
    source: str | None
    action: str | None
    record_id: str | None


def manager_invocation(*, arguments: Sequence[str]) -> Result[ManagerInvocation, ManagerError]:
    """Recognize `arguments` as one manager invocation, or refuse with the contract's type."""
    if not arguments:
        return Failure(invalid_request(message="a manager subcommand is required"))
    command = arguments[0]
    if command not in MANAGER_COMMANDS:
        return Failure(invalid_request(message="the first argument must name a manager subcommand"))
    operands = tuple(arguments[1:])
    if command == ATTENTION_COMMAND:
        return _attention_invocation(operands=operands)
    if command == PROOF_STATUS_COMMAND:
        if operands:
            return Failure(invalid_request(message="proof-status accepts no argument or flag"))
        return Success(_invocation(command=command))
    return _json_invocation(command=command, operands=operands)


def _invocation(
    *,
    command: str,
    source: str | None = None,
    action: str | None = None,
    record_id: str | None = None,
) -> ManagerInvocation:
    return ManagerInvocation(command=command, source=source, action=action, record_id=record_id)


def _json_invocation(
    *, command: str, operands: tuple[str, ...]
) -> Result[ManagerInvocation, ManagerError]:
    """One `<flag> <path|->` pair exactly, refused with this command's own error type."""
    flag = JSON_FLAG_BY_COMMAND[command]
    if len(operands) != _FLAG_AND_VALUE or operands[0] != flag or operands[1] == "":
        refuse = invalid_report if command == REPORT_COMMAND else invalid_request
        return Failure(refuse(message=f"{command} accepts exactly {flag} <path|{_STANDARD_INPUT}>"))
    return Success(_invocation(command=command, source=operands[1]))


def _attention_invocation(*, operands: tuple[str, ...]) -> Result[ManagerInvocation, ManagerError]:
    """No operand is the list action; one action flag and its record id is a mutation."""
    if not operands:
        return Success(_invocation(command=ATTENTION_COMMAND))
    if (
        len(operands) != _FLAG_AND_VALUE
        or operands[0] not in ATTENTION_ACTIONS
        or operands[1] == ""
    ):
        return Failure(
            invalid_request(
                message=(
                    "attention accepts no argument or exactly one of "
                    f"{' and '.join(f'{action} <record_id>' for action in ATTENTION_ACTIONS)}"
                )
            )
        )
    return Success(
        _invocation(command=ATTENTION_COMMAND, action=operands[0], record_id=operands[1])
    )
