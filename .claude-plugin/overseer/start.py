"""Importable entry point for the /overseer two-pane bootstrap.

This is the skill's bootstrap command — invoked BY the `/overseer` skill from
inside the interactive agent (bottom) pane. It is NOT a standalone launcher and
does NOT start Claude or Codex: it splits the daemon pane beside the SAME agent
session that ran `/overseer`, and that session simply resumes in the bottom pane.
Run by hand from a plain shell it would leave a bare-shell bottom pane (no agent),
so it REFUSES unless process ancestry shows a supported agent runtime.
"""
# livespec-lloc-soft-band-owner: overseer-4z97.2

from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import daemon_log
import legacy_start
import public_bootstrap
import runtime_prefix
import start_daemon_command
import streams
import supervisor
import terminal_probes
import tmuxio
from _seams import PidToOptionalInt, PidToOptionalStr
from claude_sessions import proc_comm, proc_ppid

__all__: list[str] = ["daemon_command", "default_core_root", "main"]

_DAEMON_PANE_TITLE = legacy_start.DAEMON_PANE_TITLE
_DAEMON_PANE_HEIGHT_PERCENT = legacy_start.DAEMON_PANE_HEIGHT_PERCENT
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
    return _default_core_root() / "tmp" / "overseer" / daemon_log.HISTORY_FILENAME


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
    """Backward-compatible private wrapper for the shared core-root resolver."""
    return default_core_root()


def default_core_root() -> Path:
    """Root whose package should win when the daemon runs ``python -m overseer.daemon``."""
    module_root = Path(__file__).resolve().parent.parent
    checkout_root = _checkout_root_from_cwd(cwd=Path.cwd(), module_root=module_root)
    if checkout_root is not None:
        return checkout_root
    return module_root if _is_checkout_root(path=module_root) else Path.cwd().resolve()


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

    The redirect only NAMES the file; it does not keep it finite. The daemon takes
    ownership of that descriptor at startup and holds the history inside
    :data:`daemon_log.DEFAULT_RETENTION` from then on (``overseerd --help`` states the
    bound, the retained generations, and the recovery procedure), which is why this
    command and the retention policy resolve the filename from the same constant.
    """
    target = log_path if log_path is not None else _default_daemon_log_path()
    return start_daemon_command.build_daemon_command(
        warn_percent=warn_percent,
        log_path=target,
        daemon_executable=daemon_executable,
    )


def _start_verified(
    *,
    warn_percent: int | None,
    build_supervisor: Callable[[], supervisor.Supervisor] | None,
    core_root: Path | None,
    ensure_daemon_runtime: Callable[[], Path | None] | None,
) -> int:
    """Run the shipped exact-instance bootstrap path."""
    if not any(
        os.environ.get(name)
        for name in (terminal_probes.TMUX_ENV, "TMUX_PANE", terminal_probes.HERDR_SOCKET_ENV)
    ):
        streams.write_stderr(
            text=(
                "overseer-start: not inside a tmux pane ($TMUX_PANE unset) and no "
                "Herdr endpoint is declared. Run /overseer from a Claude Code or "
                "Codex session inside a supported terminal pane.\n"
            )
        )
        return 1
    core = core_root if core_root is not None else _default_core_root()
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
    log_path = core / "tmp" / "overseer" / daemon_log.HISTORY_FILENAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = daemon_command(
        warn_percent=warn_percent,
        log_path=log_path,
        daemon_executable=daemon_executable,
    )
    operator_home = os.environ.get("HOME")
    if operator_home:
        command = f"HOME={shlex.quote(operator_home)} {command}"
    return public_bootstrap.run_verified_bootstrap(
        core=core,
        command=command,
        daemon_executable=daemon_executable,
        build_supervisor=build_supervisor,
    )


def main(
    *,
    argv: list[str] | None = None,
    io: tmuxio.WindowLayoutDriver | None = None,
    build_supervisor: Callable[[], supervisor.Supervisor] | None = None,
    core_root: Path | None = None,
    ensure_daemon_runtime: Callable[[], Path | None] | None = None,
) -> int:
    """Bootstrap beside the nearest verified owning tmux or Herdr pane.

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

    if io is None:
        return _start_verified(
            warn_percent=args.warn_percent,
            build_supervisor=build_supervisor,
            core_root=core_root,
            ensure_daemon_runtime=ensure_daemon_runtime,
        )
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
    ensure_runtime = (
        ensure_daemon_runtime
        if ensure_daemon_runtime is not None
        else runtime_prefix.ensure_current_runtime
    )
    return legacy_start.run_legacy_start(
        pane=pane,
        warn_percent=args.warn_percent,
        layout=io,
        build_supervisor=build_supervisor,
        core=core_root if core_root is not None else _default_core_root(),
        ensure_daemon_runtime=ensure_runtime,
    )


if __name__ == "__main__":
    raise SystemExit(main())
