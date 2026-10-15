"""Finding the sessions whose transcripts a pass may read refusals from.

The join is the one `caam_sessions` already makes for model enforcement, asked
for one more fact: a tmux pane's process tree is walked for the environment a
Claude session publishes, and both ``CLAUDE_CODE_SESSION_ID`` -- which names the
transcript -- and ``CLAUDE_CONFIG_DIR`` -- which names the credential that
session authenticates with -- are read from the SAME environment block. Reading
them together is what makes the sandbox discriminator trustworthy: the
configuration directory belongs to the very process that wrote the transcript,
rather than being inferred from where the transcript happens to sit.

A session that publishes no configuration directory is on the host's default
one, which is what the agent itself does with an unset variable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import claude_sessions
from _seams import PidToIntList, PidToOptionalBytes
from caam_picker import real_picker_tmux
from caam_refusal_attribution import LIVE_CONFIG_REL
from caam_refusals import TrackedSession
from caam_sessions import descendant_pids

__all__: list[str] = [
    "discover_tracked_sessions",
    "tracked_sessions_from_panes",
]

_SESSION_ENV_PREFIX: Final = "CLAUDE_CODE_SESSION_ID="
_CONFIG_ENV_PREFIX: Final = "CLAUDE_CONFIG_DIR="


def discover_tracked_sessions(*, home: Path) -> tuple[TrackedSession, ...]:
    """Every tracked Claude session on this host, from one tmux call and `/proc`."""
    return tracked_sessions_from_panes(
        home=home,
        pane_pids=tuple(real_picker_tmux().pane_pid_sessions()),
        children_of=claude_sessions.proc_children,
        environ_of=claude_sessions.proc_environ,
    )


def tracked_sessions_from_panes(
    *,
    home: Path,
    pane_pids: tuple[int, ...],
    children_of: PidToIntList,
    environ_of: PidToOptionalBytes,
) -> tuple[TrackedSession, ...]:
    """The tracked sessions under a given set of pane processes.

    Deduplicated by transcript id: a session reachable from two panes is one
    session, and reading its transcript twice would double every refusal it
    carries.
    """
    found: dict[str, TrackedSession] = {}
    for pane_pid in pane_pids:
        for pid in descendant_pids(root=pane_pid, children_of=children_of):
            session = _session_of(home=home, environ=environ_of(pid=pid))
            if session is not None and session.session_id not in found:
                found[session.session_id] = session
    return tuple(found.values())


def _session_of(*, home: Path, environ: bytes | None) -> TrackedSession | None:
    if not environ:
        return None
    entries = environ.decode(errors="replace").split("\0")
    session_id = _value_of(entries=entries, prefix=_SESSION_ENV_PREFIX)
    if session_id is None:
        return None
    config_dir = _value_of(entries=entries, prefix=_CONFIG_ENV_PREFIX)
    return TrackedSession(
        session_id=session_id,
        config_dir=home / LIVE_CONFIG_REL if config_dir is None else Path(config_dir),
    )


def _value_of(*, entries: list[str], prefix: str) -> str | None:
    for entry in entries:
        if entry.startswith(prefix):
            return entry.removeprefix(prefix) or None
    return None
