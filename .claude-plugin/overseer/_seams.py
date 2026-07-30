"""_seams — the injectable call shapes this package declares, as Protocols.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split.

**Why these are Protocols rather than ``Callable[[X], Y]``.** Every seam here is a
substitution point the daemon owns: a process reader, a pane predicate, a mapping-row
filter, a subcommand handler. The package's rule is that a function's parameters are
keyword-only, and ``Callable[[int], str | None]`` CANNOT EXPRESS a keyword parameter —
it can only say "one positional argument". So a `Callable`-typed seam forces every
function bound to it to stay positional, and the rule and the annotation contradict
each other. A ``Protocol`` with a keyword-only ``__call__`` states the same contract
and can express the keyword, which is why the conversion is the answer rather than an
exemption (`overseer-bg2.9`).

**Where the line falls, and it is not arbitrary.** These seams are declared by THIS
repo, so their calling convention is ours to set. A seam declared ELSEWHERE is not:
``time.sleep``, ``shutil.which``, ``subprocess.run`` and ``argparse``'s ``type=``
callback are all invoked by code we do not own, positionally, and the functions bound
to them therefore stay positional. The same asymmetry governs
``test_supervisor_fakes.TtyOut.write``, which implements the stdlib ``IO[str]``
interface and is bound rather than redefined. You can reshape your own seam; you
cannot reshape stdlib.

**Naming.** Each Protocol is named for its SHAPE, not for one role, because several
are genuinely shared — ``PidToOptionalStr`` serves the start-time, comm and cwd
readers alike. A per-role name on a shared shape would imply a distinction that does
not exist.

The keyword names in each ``__call__`` are part of the contract: a substitute must
name its parameter identically, because the caller passes it by keyword.
"""

from __future__ import annotations

import argparse
from typing import Protocol

__all__: list[str] = [
    "CommToPidList",
    "MappingRowPredicate",
    "PaneCommandPredicate",
    "PidToIntList",
    "PidToOptionalInt",
    "PidToOptionalStr",
    "PidToStrList",
    "RepoPredicate",
    "SubcommandHandler",
]


class PidToOptionalInt(Protocol):
    """Read one integer fact about a process, or None when it cannot be read."""

    def __call__(self, *, pid: int) -> int | None: ...


class PidToOptionalStr(Protocol):
    """Read one string fact about a process, or None when it cannot be read.

    Shared by the start-time, comm and cwd readers — same shape, three roles.
    """

    def __call__(self, *, pid: int) -> str | None: ...


class PidToIntList(Protocol):
    """List the process ids related to a process (empty when unreadable)."""

    def __call__(self, *, pid: int) -> list[int]: ...


class PidToStrList(Protocol):
    """List the string facts belonging to a process (empty when unreadable)."""

    def __call__(self, *, pid: int) -> list[str]: ...


class CommToPidList(Protocol):
    """List the live process ids whose comm matches (empty when none or unreadable)."""

    def __call__(self, *, comm: str) -> list[int]: ...


class RepoPredicate(Protocol):
    """Answer a yes/no question about a repo path."""

    def __call__(self, *, repo: str) -> bool: ...


class PaneCommandPredicate(Protocol):
    """Decide whether a pane's foreground command is the runtime being waited for.

    Takes the command as tmux reports it, which is None when the pane cannot be read —
    a substitute must handle that rather than assume a string.
    """

    def __call__(self, *, pane_current_command: str | None) -> bool: ...


class MappingRowPredicate(Protocol):
    """Decide whether a mapping-store row survives a rewrite."""

    def __call__(self, *, row: dict[str, object]) -> bool: ...


class SubcommandHandler(Protocol):
    """Run one CLI subcommand and return its process exit status.

    Bound via ``parser.set_defaults(func=...)`` and invoked by our own
    ``args.func(args=args)`` — argparse stores the value but never calls it, so this
    convention is ours to set, unlike ``add_argument(type=...)``, which argparse
    itself calls positionally.
    """

    def __call__(self, *, args: argparse.Namespace) -> int: ...
