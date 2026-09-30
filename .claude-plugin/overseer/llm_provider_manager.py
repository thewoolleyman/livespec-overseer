"""The shared operator entrypoint every `llm-provider-manager` harness binding delegates to.

SPECIFICATION/non-functional-requirements.md requires each manager binding to
resolve and validate the plugin root, DELEGATE TO SHARED IMPORTABLE CODE, and carry no
operation behavior of its own. This module is that shared code, and it is confined to
exactly what the contract permits the invocation layer to contain: exact argument
validation, `invalid-request` and pre-exec `internal-bug` construction, prevalidated
absolute-path executable launch, verbatim result presentation and exit-status propagation.

IT IS NOT THE MANAGER. Acquisition, validation, storage, selection, provisioning,
revalidation and replacement all live behind `<plugin-root>/bin/llm-provider-manager`,
which this layer LAUNCHES and never reimplements. The distinction is what keeps three
harness bindings honest: each of them resolves a root its own way, and then all three run
the same code from here against the same executable there. A behavior that leaked into
this layer would be a behavior one harness could get a different answer for.

THE ORDER OF THE TWO REFUSALS IS PART OF THE CONTRACT. The root is validated BEFORE the
arguments, because a mismatched manifest means this process cannot trust that it is even
looking at the right plugin — and "your arguments are wrong" is a misleading thing to say
when the question of whose argument grammar applies is still open. So a broken root and a
broken argument list together report `internal-bug`/70, not `invalid-request`/2.

NOTHING REFUSED IS EVER LAUNCHED. Both refusals are built and returned before the launch
seam is reached, which is a stronger property than mapping a non-zero exit back onto a
refusal: the manager is never asked to adjudicate a request this layer already knows is
invalid, so no partial operation, lock or worker can result from one.

THE LAUNCH TARGET IS THE ROOT'S OWN ABSOLUTE PATH, never a `PATH` lookup. The contract
forbids searching consumer `PATH` because that would run whichever manager the consumer's
environment happened to expose — a different version, or a different plugin entirely —
against state this plugin's prose just told the operator about.

PRESENTATION IS VERBATIM. The executable's single JSON line is passed through unparsed and
its exit status unchanged. Re-serializing would silently normalize member order and
whitespace, and the consumer wire protocol is specified on those bytes; collapsing an
unfamiliar exit status onto a familiar one would turn a typed failure into a retryable
one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import streams
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_binding_root import validated_plugin_root
from _lpm_operator_request import operator_request
from _lpm_results import ManagerError, error_object, exit_status_for, internal_bug

from overseer._vendor.returns.result import Failure

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "MANAGER_EXECUTABLE_RELATIVE_PATH",
    "Launch",
    "LaunchResult",
    "OperatorPresentation",
    "default_plugin_root",
    "main",
    "manager_executable",
    "run_operator_invocation",
    "subprocess_launch",
]

MANAGER_EXECUTABLE_RELATIVE_PATH: Final = "bin/llm-provider-manager"


@dataclass(frozen=True, kw_only=True)
class LaunchResult:
    """What the manager executable answered: its one JSON line and its exit status."""

    stdout: str
    exit_status: int


@dataclass(frozen=True, kw_only=True)
class OperatorPresentation:
    """What the binding presents to the operator, and the status it reports back."""

    stdout: str
    exit_status: int


class Launch(Protocol):
    def __call__(
        self, *, executable: Path, argv: tuple[str, ...], stdin_bytes: bytes | None
    ) -> LaunchResult: ...


def default_plugin_root() -> Path:
    """The plugin root containing THIS copy of the package.

    SPECIFICATION/contracts.md requires the plugin executable to resolve its product
    package only from `<plugin-root>/overseer/`, never from a separately installed
    `overseer`. Deriving the root from this module's own location is what makes that
    true structurally: the shipped mirror resolves the plugin that carries it, and no
    environment variable a consumer controls can repoint it at another plugin's state.
    """
    return Path(__file__).resolve().parent.parent


def manager_executable(*, plugin_root: Path) -> Path:
    """The one absolute path this layer may launch."""
    return plugin_root / "bin" / "llm-provider-manager"


def subprocess_launch(
    *, executable: Path, argv: tuple[str, ...], stdin_bytes: bytes | None
) -> LaunchResult:
    """Run the manager executable by absolute path, streaming any request to its stdin.

    `stdin_bytes` is `None` for the attention list, which takes no standard input; the
    acquisition object is streamed over the pipe rather than written to a temporary file,
    which the contract requires and which also keeps the request off the filesystem.
    """
    completed = subprocess.run(  # noqa: S603 - absolute, prevalidated path; never PATH
        [str(executable), *argv],
        input=stdin_bytes,
        stdout=subprocess.PIPE,
        check=False,
    )
    return LaunchResult(
        stdout=completed.stdout.decode("utf-8", errors="replace"),
        exit_status=completed.returncode,
    )


def _presented(*, error: ManagerError) -> OperatorPresentation:
    """The common single-line error object, with the contract's exit status for its type."""
    return OperatorPresentation(
        stdout=json.dumps(error_object(error=error), separators=(",", ":")),
        exit_status=exit_status_for(error_type=error.error_type),
    )


def run_operator_invocation(
    *, arguments: Sequence[str], plugin_root: Path, launch: Launch
) -> OperatorPresentation:
    """Validate the root, then the arguments, then launch — or refuse before any launch."""
    root = validated_plugin_root(plugin_root=plugin_root)
    if isinstance(root, Failure):
        return _presented(error=root.failure())

    request = operator_request(arguments=arguments)
    if isinstance(request, Failure):
        return _presented(error=request.failure())
    accepted = request.unwrap()

    try:
        result = launch(
            executable=manager_executable(plugin_root=root.unwrap()),
            argv=accepted.argv,
            stdin_bytes=accepted.stdin_bytes,
        )
    except (OSError, subprocess.SubprocessError):
        # The contract's OTHER `internal-bug`: a missing, non-regular or non-executable
        # plugin path, or a launch that failed before any valid manager JSON result. The
        # caught exception is deliberately NOT quoted into the message -- an operating
        # system error string can carry the argument vector, and this operation's output
        # is required to be secret-free.
        return _presented(
            error=internal_bug(message=f"{MANAGER_EXECUTABLE_RELATIVE_PATH} could not be launched")
        )
    return OperatorPresentation(stdout=result.stdout, exit_status=result.exit_status)


def main() -> int:
    """The console seam: real argv, the carrier's own root, a real subprocess launch.

    Deliberately branchless. Every substitutable collaborator is a parameter of
    :func:`run_operator_invocation` instead of an optional argument here, so this
    function has no default-resolution branch that could behave differently under a
    test than it does in a plugin.
    """
    presentation = run_operator_invocation(
        arguments=sys.argv[1:],
        plugin_root=default_plugin_root(),
        launch=subprocess_launch,
    )
    streams.write_stdout(text=f"{presentation.stdout}\n")
    return presentation.exit_status


if __name__ == "__main__":
    raise SystemExit(main())
