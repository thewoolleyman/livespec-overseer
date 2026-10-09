"""Deterministic companion coverage for tmux retained-shell daemon evidence.

The frozen native regression proves the behavior through public
``overseer-start``.  These cases keep the bounded process walk and its fail-closed
edges gradeable on hosts without a native tmux/Herdr nesting setup; they are
postimplementation companion coverage, not a reconstructed Red receipt.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from overseer import (
    claude_sessions,
    terminal_ownership,
    terminal_probes,
    tmux_bootstrap,
    tmux_daemon_liveness,
)

__all__: list[str] = []


def test_daemon_descendant_walk_is_bounded_cycle_safe_and_excludes_the_shell() -> None:
    children = {10: [10, 20], 20: [30], 30: [20]}
    commands = {20: None, 30: b"/candidate/bin/python\0/candidate/bin/overseerd\0"}
    read: list[int] = []

    def children_of(*, pid: int) -> list[int]:
        return list(children.get(pid, []))

    def cmdline_of(*, pid: int) -> bytes | None:
        read.append(pid)
        return commands.get(pid)

    command = tmux_daemon_liveness.daemon_descendant_command(
        root_pid=10,
        children_of=children_of,
        cmdline_of=cmdline_of,
    )

    assert command == "/candidate/bin/python /candidate/bin/overseerd"
    assert 10 not in read

    def unreadable(*, pid: int) -> None:
        del pid

    assert (
        tmux_daemon_liveness.daemon_descendant_command(
            root_pid=10,
            children_of=children_of,
            cmdline_of=unreadable,
            max_processes=1,
        )
        is None
    )


def test_descendant_walk_refuses_unreadable_non_daemon_and_cyclic_evidence() -> None:
    children = {10: [20], 20: [30], 30: [20]}
    commands = {20: None, 30: b"python\0worker.py\0"}

    def children_of(*, pid: int) -> list[int]:
        return list(children.get(pid, []))

    def cmdline_of(*, pid: int) -> bytes | None:
        return commands.get(pid)

    assert (
        tmux_daemon_liveness.daemon_descendant_command(
            root_pid=10,
            children_of=children_of,
            cmdline_of=cmdline_of,
        )
        is None
    )


def _native_tmux(
    *, socket_path: str, tmux_binary: str, args: list[str]
) -> subprocess.CompletedProcess[str]:
    run = terminal_probes.SocketScopedRun(socket_path=socket_path)
    return run(
        [tmux_binary, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30.0,
    )


def _must_native_tmux(*, socket_path: str, tmux_binary: str, args: list[str]) -> str:
    completed = _native_tmux(socket_path=socket_path, tmux_binary=tmux_binary, args=args)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _start_candidate_process(
    *, socket_path: str, tmux_binary: str, pane: str, tmp_path: Path, case: str
) -> None:
    if case == "background-daemon":
        candidate_home = tmp_path / "candidate-home"
        candidate_home.mkdir()
        daemon_executable = Path(__file__).resolve().parent.parent / ".venv/bin/overseerd"
        command = (
            f"HOME={shlex.quote(str(candidate_home))} "
            f"{shlex.quote(str(daemon_executable))} --idle-nudge off "
            f">/dev/null 2>{shlex.quote(str(tmp_path / 'background-daemon.log'))} &"
        )
    else:
        marker_fifo = tmp_path / "overseerd"
        os.mkfifo(marker_fifo)
        cat_binary = shutil.which("cat")
        assert cat_binary is not None
        command = f"{shlex.quote(cat_binary)} {shlex.quote(str(marker_fifo))}"
    _ = _must_native_tmux(
        socket_path=socket_path,
        tmux_binary=tmux_binary,
        args=["send-keys", "-t", pane, "-l", command],
    )
    _ = _must_native_tmux(
        socket_path=socket_path,
        tmux_binary=tmux_binary,
        args=["send-keys", "-t", pane, "Enter"],
    )


@pytest.mark.parametrize("case", ["background-daemon", "foreground-cat"])
def test_native_tmux_unowned_process_cannot_authorize_reuse(*, tmp_path: Path, case: str) -> None:
    tmux_binary = shutil.which("tmux")
    if tmux_binary is None:
        pytest.skip("tmux is unavailable")
    socket_path = str(tmp_path / "owned-tmux.sock")

    try:
        caller = _must_native_tmux(
            socket_path=socket_path,
            tmux_binary=tmux_binary,
            args=[
                "new-session",
                "-d",
                "-P",
                "-F",
                "#{pane_id}",
                "-s",
                "owned",
                "-c",
                str(tmp_path),
            ],
        )
        candidate = _must_native_tmux(
            socket_path=socket_path,
            tmux_binary=tmux_binary,
            args=[
                "split-window",
                "-v",
                "-b",
                "-d",
                "-P",
                "-F",
                "#{pane_id}",
                "-t",
                caller,
                "-c",
                str(tmp_path),
            ],
        )
        _start_candidate_process(
            socket_path=socket_path,
            tmux_binary=tmux_binary,
            pane=candidate,
            tmp_path=tmp_path,
            case=case,
        )
        pane_pid = int(
            _must_native_tmux(
                socket_path=socket_path,
                tmux_binary=tmux_binary,
                args=["display-message", "-p", "-t", candidate, "#{pane_pid}"],
            )
        )
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            command = tmux_daemon_liveness.daemon_descendant_command(root_pid=pane_pid)
            if command is not None and tmux_daemon_liveness.is_daemon_argv(command=command):
                break
            time.sleep(0.05)
        else:
            pytest.fail(f"the native {case} process did not start")
        server_pid = int(
            _must_native_tmux(
                socket_path=socket_path,
                tmux_binary=tmux_binary,
                args=["display-message", "-p", "-t", caller, "#{pid}"],
            )
        )
        server_starttime = claude_sessions.proc_starttime(pid=server_pid)
        assert server_starttime is not None
        caller_pid = int(
            _must_native_tmux(
                socket_path=socket_path,
                tmux_binary=tmux_binary,
                args=["display-message", "-p", "-t", caller, "#{pane_pid}"],
            )
        )
        claim = terminal_ownership.OwnershipClaim(
            backend="tmux",
            socket_path=socket_path,
            server_pid=server_pid,
            server_starttime=server_starttime,
            pane_id=caller,
            pane_process_pid=caller_pid,
            distance=1,
        )

        reading = tmux_bootstrap.TmuxBootstrap().daemon_host(claim=claim)

        assert reading.pane_id == ""
        assert "fresh exact-instance, pane and process evidence" in reading.unresolved
    finally:
        if Path(socket_path).exists():
            _ = _native_tmux(
                socket_path=socket_path,
                tmux_binary=tmux_binary,
                args=["kill-server"],
            )


@dataclass(frozen=True, kw_only=True)
class _Geometry:
    pane: str
    top: int
    height: int


@dataclass(frozen=True, kw_only=True)
class _RetainedShellDriver:
    pane_pid_value: int | None

    def window_pane_geometries(self, *, pane: str) -> list[_Geometry]:
        del pane
        return [
            _Geometry(pane="%daemon", top=0, height=20),
            _Geometry(pane="%caller", top=20, height=10),
        ]

    def pane_current_command(self, *, session: str) -> str:
        del session
        return "bash"

    def pane_pid(self, *, session: str) -> int | None:
        del session
        return self.pane_pid_value


def _claim() -> terminal_ownership.OwnershipClaim:
    return terminal_ownership.OwnershipClaim(
        backend="tmux",
        socket_path="/tmp/named.sock",
        server_pid=30,
        server_starttime="generation",
        pane_id="%caller",
        pane_process_pid=20,
        distance=1,
    )


def test_tmux_host_reuses_shell_pane_only_with_fresh_daemon_descendant(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = _RetainedShellDriver(pane_pid_value=10)

    def daemon_process(*, root_pid: int) -> object | None:
        return object() if root_pid == 10 else None

    monkeypatch.setattr(
        tmux_bootstrap.tmux_daemon_liveness,
        "foreground_daemon_process",
        daemon_process,
        raising=False,
    )

    def daemon_command(*, root_pid: int) -> str | None:
        return "/candidate/bin/overseerd" if root_pid == 10 else None

    monkeypatch.setattr(
        tmux_bootstrap.tmux_daemon_liveness,
        "daemon_descendant_command",
        daemon_command,
    )

    def driver_for(*, socket_path: str) -> _RetainedShellDriver:
        del socket_path
        return driver

    backend = tmux_bootstrap.TmuxBootstrap(driver_for=driver_for)

    reading = backend.daemon_host(claim=_claim())

    assert (reading.pane_id, reading.unresolved, reading.error) == ("%daemon", "", "")


def test_tmux_host_refuses_shell_when_its_root_process_is_unreadable() -> None:
    driver = _RetainedShellDriver(pane_pid_value=None)

    def driver_for(*, socket_path: str) -> _RetainedShellDriver:
        del socket_path
        return driver

    backend = tmux_bootstrap.TmuxBootstrap(driver_for=driver_for)

    reading = backend.daemon_host(claim=_claim())

    assert reading.pane_id == ""
    assert "retained shell" in reading.unresolved
