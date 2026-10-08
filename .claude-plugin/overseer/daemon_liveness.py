"""daemon_liveness.py — recognizing a LIVE overseer daemon in a pane.

The one shared question both bootstrap backends have to answer about a pane
sitting above the invoking one: is the overseer daemon RUNNING in it? Shared
rather than duplicated because the two backends read different evidence — herdr
answers with a pane process reading over its socket, tmux with
`#{pane_current_command}` — but they must agree on what counts, and a second
spelling of the marker set is a second thing to drift.

**A RETAINED SHELL IS NOT DAEMON LIVENESS, and that distinction is the whole
reason this module exists.** Both backends keep the pane's own shell alive and run
the daemon as a child of it, so a pane that still exists after its daemon died
looks, structurally, exactly like a pane whose daemon never started. The pane's
continued existence proves nothing about the process; only the process does.
Treating the shell as the daemon would make a dead daemon read as a healthy one —
and because the bootstrap REUSES a verified daemon pane rather than splitting
again, that reading would leave the operator with no daemon at all and no
indication of it.

**The marker set is the two spellings the launcher actually produces.** The
installed console script is `overseerd`, and `.claude-plugin/bin/overseerd` ends by
`exec`ing `python3 -m overseer.daemon` — so a healthy daemon's process title is the
module invocation rather than the script name, and matching only one of the two
would miss every daemon started the other way. The match is a SUBSTRING because
what is read back is a full command line carrying an absolute interpreter path, a
prefix, and the daemon's own flags.

**`is_retained_shell` exists to make a refusal SPECIFIC rather than to authorize
anything.** Nothing is ever accepted because it is a shell; the predicate only lets
the diagnostic say "that pane is holding its shell" instead of "that pane is not
the daemon", which is the difference between an operator knowing the daemon died
and an operator knowing only that something is up there. A leading `-` is stripped
because a login shell's `argv[0]` conventionally carries one.
"""

from __future__ import annotations

__all__: list[str] = [
    "DAEMON_COMMAND_MARKERS",
    "RETAINED_SHELL_NAMES",
    "is_daemon_command",
    "is_retained_shell",
]

DAEMON_COMMAND_MARKERS = ("overseerd", "overseer.daemon")
RETAINED_SHELL_NAMES = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh"})


def is_daemon_command(*, text: str) -> bool:
    """Whether `text` names the overseer daemon rather than something else."""
    return any(marker in text for marker in DAEMON_COMMAND_MARKERS)


def is_retained_shell(*, name: str) -> bool:
    """Whether `name` is a login shell of the kind that holds a pane open."""
    return name.lstrip("-") in RETAINED_SHELL_NAMES
