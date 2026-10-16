"""Validate the manager command vector before configuration or state access."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_commands import ManagerInvocation
from _lpm_results import ManagerError, invalid_report, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "JSON_FLAG_BY_COMMAND",
    "manager_invocation",
]

JSON_FLAG_BY_COMMAND: Final[dict[str, str]] = {
    "acquire": "--acquisition-json",
    "target": "--target-json",
    "provision": "--request-json",
    "report": "--report-json",
}
_OBJECT_COMMAND_ARGUMENTS: Final = 3


def manager_invocation(*, arguments: Sequence[str]) -> Result[ManagerInvocation, ManagerError]:
    """Recognize the installed runtime's closed command and operand shapes."""
    if not arguments:
        return Success(ManagerInvocation(command="attention", source=None))
    command = arguments[0]
    if command == "attention":
        if len(arguments) == 1:
            return Success(ManagerInvocation(command=command, source=None))
        return Failure(invalid_request(message="attention accepts no argument or flag"))
    flag = JSON_FLAG_BY_COMMAND.get(command)
    if flag is None:
        return Failure(invalid_request(message="the first argument must name a manager command"))
    if len(arguments) != _OBJECT_COMMAND_ARGUMENTS or arguments[1] != flag or arguments[2] == "":
        refuse = invalid_report if command == "report" else invalid_request
        return Failure(refuse(message=f"{command} accepts exactly {flag} <path|->"))
    return Success(ManagerInvocation(command=command, source=arguments[2]))
