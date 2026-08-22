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
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runtime_prefix
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


def _default_daemon_log_path() -> Path:
    """Default daemon log location beside the daemon import root."""
    return _default_core_root() / "tmp" / "overseer" / "daemon.log"


def _is_checkout_root(*, path: Path) -> bool:
    package = path / "overseer"
    return (package / "start.py").is_file()


def _checkout_root_from_cwd(*, cwd: Path, module_root: Path) -> Path | None:
    resolved = cwd.resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate != module_root and _is_checkout_root(path=candidate):
            return candidate
    return None


def _default_core_root() -> Path:
    """Root whose package should win when the daemon runs ``python -m overseer.daemon``."""
    module_root = Path(__file__).resolve().parent.parent
    checkout_root = _checkout_root_from_cwd(cwd=Path.cwd(), module_root=module_root)
    return checkout_root if checkout_root is not None else module_root


def daemon_command(
    *,
    warn_percent: int | None,
    log_path: Path | None = None,
    daemon_executable: Path | None = None,
) -> str:
    """The `overseerd` launch command for the daemon top pane.

    When ``warn_percent`` is given it is threaded through to the daemon as
    ``--warn-percent N`` (the daemon-wide first-wrap-up threshold); stderr is
    redirected to the daemon log the bottom pane reads for alerts. The redirect
    target is absolute so the daemon launch never depends on the repo where the
    operator invoked ``/overseer``.
    """
    base = shlex.quote(str(daemon_executable)) if daemon_executable is not None else "overseerd"
    if warn_percent is not None:
        base += f" --warn-percent {warn_percent}"
    target = log_path if log_path is not None else _default_daemon_log_path()
    return base + f" 2>> {shlex.quote(str(target))}"


_daemon_command = daemon_command


def _start_daemon_pane(
    *,
    layout: tmuxio.WindowLayoutDriver,
    pane: str,
    core: Path,
    warn_percent: int | None,
    daemon_executable: Path,
) -> bool:
    log_path = core / "tmp" / "overseer" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = daemon_command(
        warn_percent=warn_percent,
        log_path=log_path,
        daemon_executable=daemon_executable,
    )
    new_pane = layout.split_window_top(pane=pane, cwd=str(core), command=command)
    if new_pane is None:
        streams.write_stderr(
            text="overseer-start: FAILED to split the window for the daemon pane.\n"
        )
        return False
    _ = layout.set_pane_title(pane=new_pane, title=_DAEMON_PANE_TITLE)
    if not layout.pane_exists(pane=new_pane):
        streams.write_stderr(
            text=(
                "overseer-start: overseerd did not stay alive in the daemon pane; "
                f"check {log_path} for startup errors.\n"
            )
        )
        return False
    streams.write_stderr(text=f"overseer-start: started overseerd in top pane {new_pane}.\n")
    return True


def main(
    *,
    argv: list[str] | None = None,
    io: tmuxio.WindowLayoutDriver | None = None,
    build_supervisor: Callable[[], supervisor.Supervisor] | None = None,
    core_root: Path | None = None,
    ensure_daemon_runtime: Callable[[], Path | None] | None = None,
) -> int:
    """Bootstrap the two-pane overseer layout in the CURRENT tmux window.

    ``io``, ``build_supervisor``, and ``core_root`` are injectable for the same
    reason ``Supervisor.tmux`` is: everything below them is orchestration — the
    idempotency check, the failure handling, the resize — and orchestration that
    can only be exercised by really splitting a live tmux window is orchestration
    that never gets exercised. The shipped call path uses the real implementations
    and the operator checkout when the skill launcher was imported from a plugin
    build.

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

    # Prefer the operator checkout over a plugin build that imported this module;
    # cwd wins Python's module resolution for `python -m` when it contains overseer.
    core = core_root if core_root is not None else _default_core_root()
    layout: tmuxio.WindowLayoutDriver = io if io is not None else tmuxio.TmuxIO()

    # 1. Start the daemon in a TOP pane of THIS window (idempotent).
    if _DAEMON_PANE_TITLE in layout.window_pane_titles(pane=pane):
        streams.write_stderr(
            text="overseer-start: daemon pane already present in this window; leaving it.\n"
        )
    else:
        ensure_runtime = (
            ensure_daemon_runtime
            if ensure_daemon_runtime is not None
            else runtime_prefix.ensure_current_runtime
        )
        daemon_executable = ensure_runtime()
        if daemon_executable is None:
            streams.write_stderr(
                text=(
                    "overseer-start: failed to prepare the daemon-owned runtime prefix; "
                    "overseerd was not launched from the working tree.\n"
                )
            )
            return 1
        if not _start_daemon_pane(
            layout=layout,
            pane=pane,
            core=core,
            warn_percent=args.warn_percent,
            daemon_executable=daemon_executable,
        ):
            return 1

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
