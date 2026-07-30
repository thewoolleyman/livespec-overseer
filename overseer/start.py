"""Importable entry point for the /overseer two-pane bootstrap.

This is the skill's bootstrap command — invoked BY the `/overseer` skill from
inside the interactive agent (bottom) pane. It is NOT a standalone launcher and
does NOT start Claude or Codex: it splits the daemon pane beside the SAME agent
session that ran `/overseer`, and that session simply resumes in the bottom pane.
Run by hand from a plain shell it would leave a bare-shell bottom pane (no agent),
so it REFUSES unless process ancestry shows a supported agent runtime.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streams
import supervisor
import tmuxio
from _seams import PidToOptionalInt, PidToOptionalStr
from claude_sessions import proc_comm, proc_ppid

__all__: list[str] = ["daemon_command", "main"]

_DAEMON_PANE_TITLE = "overseer-daemon"

# The daemon pane's share of the window height. It carries the live table AND the
# `NEEDS YOU` block — the surfaces that actually answer "what needs my attention?" —
# so it gets the room; the bottom pane is a command prompt (maintainer 2026-07-14).
_DAEMON_PANE_HEIGHT_PERCENT = 66
_MAX_PARENT_WALK = 64
_CODEX_AGENT_COMMS = frozenset({"codex", "codex-acp"})
_CLAUDE_AGENT_COMMS = frozenset({"claude", "node"})


def _has_supported_agent_ancestor(
    *,
    pid: int,
    claudecode_present: bool,
    comm_of: PidToOptionalStr = proc_comm,
    ppid_of: PidToOptionalInt = proc_ppid,
    max_hops: int = _MAX_PARENT_WALK,
) -> bool:
    """True when ``pid`` is descended from a supported interactive agent runtime."""
    current = pid
    for _ in range(max_hops):
        comm = comm_of(pid=current)
        if comm in _CODEX_AGENT_COMMS:
            return True
        if (
            claudecode_present
            and comm is not None
            and (comm in _CLAUDE_AGENT_COMMS or "claude" in comm)
        ):
            return True
        parent = ppid_of(pid=current)
        if parent is None or parent <= 0 or parent == current:
            return False
        current = parent
    return False


def _running_under_supported_agent() -> bool:
    """Whether this bootstrap was launched by a supported agent runtime."""
    return _has_supported_agent_ancestor(
        pid=os.getpid(),
        claudecode_present=bool(os.environ.get("CLAUDECODE")),
    )


def daemon_command(*, warn_percent: int | None) -> str:
    """The `overseerd` launch command for the daemon top pane.

    When ``warn_percent`` is given it is threaded through to the daemon as
    ``--warn-percent N`` (the daemon-wide first-wrap-up threshold); stderr is
    redirected to the daemon log the bottom pane reads for alerts.
    """
    base = "overseerd"
    if warn_percent is not None:
        base += f" --warn-percent {warn_percent}"
    return base + " 2>> tmp/overseer/daemon.log"


_daemon_command = daemon_command


def main(
    *,
    argv: list[str] | None = None,
    io: tmuxio.WindowLayoutDriver | None = None,
    build_supervisor: Callable[[], supervisor.Supervisor] | None = None,
    core_root: Path | None = None,
) -> int:
    """Bootstrap the two-pane overseer layout in the CURRENT tmux window.

    ``io``, ``build_supervisor``, and ``core_root`` are injectable for the same
    reason ``Supervisor.tmux`` is: everything below them is orchestration — the
    idempotency check, the failure handling, the resize — and orchestration that
    can only be exercised by really splitting a live tmux window is orchestration
    that never gets exercised. They default to the real implementations and the
    real repo root, so the shipped call path is unchanged.

    ``core_root`` in particular keeps the daemon's marker-directory ``mkdir`` out
    of the real checkout when a test drives the split path.
    """
    parser = argparse.ArgumentParser(
        prog="overseer-start",
        description="the /overseer skill's two-pane bootstrap",
    )
    _ = parser.add_argument(
        "--warn-percent",
        type=int,
        default=None,
        metavar="N",
        help=(
            "daemon-wide default remaining-context %% at which the first wrap-up "
            "fires (default 50); passed through to overseerd"
        ),
    )
    args = parser.parse_args(argv)

    # 0. Refuse unless run BY the /overseer skill inside a supported agent runtime.
    # Env markers are inherited by child processes, so `$CLAUDECODE` alone is not
    # enough: a nested Codex launched from Claude Code inherits it. Instead walk
    # upward through process ancestry and admit a real Claude Code or Codex ancestor.
    # Without that, the bottom pane is not an agent session that will resume after
    # the split, so splitting would leave a bare-shell bottom pane — the broken
    # state this guard prevents. Refuse BEFORE splitting so no half-set-up state is
    # created.
    if not _running_under_supported_agent():
        streams.write_stderr(
            text=(
                "overseer-start: this is the /overseer skill's bootstrap, not a standalone "
                "command. Run /overseer inside a Claude Code or Codex session that is "
                "running in a tmux pane — it splits the daemon pane beside THAT session; "
                "it does NOT launch Claude or Codex. Refusing to run outside Claude Code "
                "or Codex (no supported agent runtime in process ancestry).\n"
            )
        )
        return 1

    pane = os.environ.get("TMUX_PANE")
    if not pane:
        streams.write_stderr(
            text=(
                "overseer-start: not inside a tmux pane ($TMUX_PANE unset). Run /overseer "
                "from a Claude Code or Codex session that is itself running inside a tmux "
                "pane.\n"
            )
        )
        return 1

    # …/overseer → this checkout root.
    core = core_root if core_root is not None else Path(__file__).resolve().parent.parent
    layout: tmuxio.WindowLayoutDriver = io if io is not None else tmuxio.TmuxIO()

    # 1. Start the daemon in a TOP pane of THIS window (idempotent).
    if _DAEMON_PANE_TITLE in layout.window_pane_titles(pane=pane):
        streams.write_stderr(
            text="overseer-start: daemon pane already present in this window; leaving it.\n"
        )
    else:
        (core / "tmp" / "overseer").mkdir(parents=True, exist_ok=True)
        command = daemon_command(warn_percent=args.warn_percent)
        new_pane = layout.split_window_top(pane=pane, cwd=str(core), command=command)
        if new_pane is None:
            streams.write_stderr(
                text="overseer-start: FAILED to split the window for the daemon pane.\n"
            )
            return 1
        _ = layout.set_pane_title(pane=new_pane, title=_DAEMON_PANE_TITLE)
        streams.write_stderr(text=f"overseer-start: started overseerd in top pane {new_pane}.\n")

    # 1b. Normalize the stack (self-heals an uneven split — e.g. after a stray third
    # pane was opened and closed, redistributing rows), THEN give the daemon its share.
    # The daemon pane is the one that must be readable: it carries the live table AND
    # the `NEEDS YOU` block, which is where the operator learns what wants them. The
    # bottom pane is a command prompt and needs far less room. Resolve the daemon pane
    # BY TITLE rather than reusing `new_pane`, so the idempotent re-run path (where the
    # pane already existed and we never held its id) resizes it too.
    _ = layout.select_layout_even(pane=pane)
    daemon_pane = layout.pane_by_title(pane=pane, title=_DAEMON_PANE_TITLE)
    if daemon_pane is not None:
        _ = layout.set_pane_height_percent(pane=daemon_pane, percent=_DAEMON_PANE_HEIGHT_PERCENT)

    # 2. Adopt existing worker sessions that match active plan topics.
    build = build_supervisor if build_supervisor is not None else supervisor.build_supervisor
    adopted = build().adopt_sessions()
    for track in adopted:
        streams.write_stderr(
            text=f"overseer-start: adopted {track.tmux} → {track.repo}::{track.topic}\n"
        )
    streams.write_stderr(text=f"overseer-start: adopted {len(adopted)} existing session(s).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
