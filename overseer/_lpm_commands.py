"""THE shared importable command implementation both manager launchers delegate to.

SPECIFICATION/contracts.md requires this repository's package metadata to "declare a console
entry point named `llm-provider-manager` mapped to the manager executable", and requires the
plugin executable `<plugin-root>/bin/llm-provider-manager` to resolve its product package "only
from `<plugin-root>/overseer/`". Two launchers, two package roots, ONE implementation: whichever
tree a process resolved, it reaches `run_manager_command` here, so a behaviour cannot differ
between the console path and the plugin path.

THE DISPATCH IS A FLAT TABLE OVER AN ALREADY-RECOGNIZED INVOCATION. `_lpm_manager_argv` has
settled the subcommand and its flag cardinality before this module runs, which is what makes the
contract's "a missing or unknown subcommand MUST ... [be refused] before configuration, recovery
or external access" structural: there is no configuration read and no host built until an
invocation has been recognized.

THE FOUR COMMANDS THIS BUILD SERVES are `target`, `provision`, `report` and the zero-argument
`attention` list. The other ratified subcommands are RECOGNIZED -- so their flag grammar is
validated and their refusals are typed correctly -- and answered `internal-bug` with exit `70`,
which the contract permits for every one of them. That is deliberate and it is the honest shape
for a surface whose work lives in separate, named, still-open plan children:

* `acquire` is the headed-browser acquisition flow, with its agent roles, browser control and
  attention artifacts.
* `proof-status` reads the seven-day coexistence proof record that flow produces.
* `complete` and `release` close out an assignment through the operation write-ahead records and
  tombstone protocol.
* `attention --resolve` / `--give-up` mutate a pending artifact under its own artifact lock, and
  the contract forbids a harness binding from even constructing those vectors.

`internal-bug` is the right type for each, and the reasoning is worth keeping because the two
alternatives are both lies. `invalid-request` would blame the caller for a correctly-formed,
ratified request. `store-unavailable` would blame 1Password for a gap in this build. A manager
that cannot honour a contracted request HAS an internal defect, and exit `70` is the status that
tells a consumer not to retry -- which is exactly right, because retrying will not help until
the work lands.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_attention import attention_item_object, attention_items
from _lpm_command_host import CommandOutcome, ManagerHost, error_outcome, success_outcome
from _lpm_command_provision import run_provision_command
from _lpm_command_report import run_report_command
from _lpm_command_target import run_target_command
from _lpm_manager_argv import ManagerInvocation, manager_invocation
from _lpm_results import internal_bug

from overseer._vendor.returns.result import Failure

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ATTENTION_OPERATION",
    "SERVED_COMMANDS",
    "run_manager_command",
    "run_recognized_invocation",
]

ATTENTION_OPERATION: Final = "attention"

SERVED_COMMANDS: Final = ("target", "provision", "report", "attention")


def run_manager_command(*, arguments: Sequence[str], host: ManagerHost) -> CommandOutcome:
    """Recognize `arguments`, then run the command it names against `host`."""
    invocation = manager_invocation(arguments=arguments)
    if isinstance(invocation, Failure):
        return error_outcome(error=invocation.failure())
    return run_recognized_invocation(invocation=invocation.unwrap(), host=host)


# The three served object-carrying commands, keyed by subcommand. A table rather than a chain of
# branches so that "which commands does this build serve?" is one readable value -- and so adding
# the next one is an entry here rather than another leg in a dispatcher.
_OBJECT_COMMANDS: Final[dict[str, Callable[..., CommandOutcome]]] = {
    "target": run_target_command,
    "provision": run_provision_command,
    "report": run_report_command,
}


def run_recognized_invocation(
    *, invocation: ManagerInvocation, host: ManagerHost
) -> CommandOutcome:
    """Run one already-recognized invocation; an unserved ratified command is `internal-bug`."""
    if invocation.command == ATTENTION_OPERATION:
        if invocation.action is not None:
            return _unserved(command=f"{ATTENTION_OPERATION} {invocation.action}")
        return _attention(host=host)
    run = _OBJECT_COMMANDS.get(invocation.command)
    if run is None or invocation.source is None:
        return _unserved(command=invocation.command)
    return run(source=invocation.source, host=host)


def _attention(*, host: ManagerHost) -> CommandOutcome:
    """The zero-argument list: every pending artifact, or the store-outage refusal."""
    listed = attention_items(state_dir=host.state_dir, owner_uid=host.owner_uid)
    if isinstance(listed, Failure):
        return error_outcome(error=listed.failure())
    return success_outcome(
        payload={
            "operation": ATTENTION_OPERATION,
            "items": [attention_item_object(item=item) for item in listed.unwrap()],
        }
    )


def _unserved(*, command: str) -> CommandOutcome:
    """A ratified subcommand whose work this build does not yet compose.

    The command NAME is safe to quote: it came out of `_lpm_manager_argv`'s closed table, so it
    is one of a fixed set of literals rather than anything the caller supplied.
    """
    return error_outcome(
        error=internal_bug(message=f"the {command} command is not composed in this build")
    )
