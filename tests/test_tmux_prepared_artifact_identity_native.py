"""Native refusal of a same-runtime, same-basename unprepared foreground script.

The behavioral Red for prepared-runtime compatibility is frozen in
``test_overseer_start_public_nested_tmux``.  This postimplementation companion
records the artifact-role edge found during review: even the exact prepared
Python, a stable process identity and ownership of the pane foreground do not
authorize an unrelated script merely because that script is named
``overseerd``.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from overseer import (
    claude_sessions,
    runtime_prefix,
    terminal_ownership,
    tmux_bootstrap,
    tmux_daemon_liveness,
)

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parent.parent
WAIT_SECONDS = 30.0


@dataclass(frozen=True, kw_only=True)
class ProcessObservation:
    pid: int
    starttime: str
    executable: Path
    argv: tuple[str, ...]
    process_group: int
    foreground_group: int


@dataclass(frozen=True, kw_only=True)
class NativeCase:
    binary: str
    socket_path: str
    candidate_root: int
    daemon_executable: Path
    daemon_runtime: Path
    lookalike: Path
    claim: terminal_ownership.OwnershipClaim


def _tmux(*, binary: str, socket_path: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- this test owns the named native server.
        [binary, "-S", socket_path, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30.0,
    )


def _must_tmux(*, binary: str, socket_path: str, args: list[str]) -> str:
    completed = _tmux(binary=binary, socket_path=socket_path, args=args)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _status(*, pid: int) -> tuple[int, int, str] | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rpartition(") ")[2].split()
        return int(fields[2]), int(fields[5]), fields[19]
    except (OSError, IndexError, ValueError):
        return None


def _observe(*, pid: int) -> ProcessObservation | None:
    status = _status(pid=pid)
    command = claude_sessions.proc_cmdline(pid=pid)
    starttime = claude_sessions.proc_starttime(pid=pid)
    if status is None or command is None or starttime is None:
        return None
    try:
        executable = Path(f"/proc/{pid}/exe").readlink().resolve(strict=True)
    except OSError:
        return None
    process_group, foreground_group, stat_starttime = status
    if starttime != stat_starttime:
        return None
    return ProcessObservation(
        pid=pid,
        starttime=starttime,
        executable=executable,
        argv=tuple(part.decode(errors="surrogateescape") for part in command.split(b"\0") if part),
        process_group=process_group,
        foreground_group=foreground_group,
    )


def _lookalike_below(*, root_pid: int, lookalike: Path) -> ProcessObservation | None:
    pending = list(claude_sessions.proc_children(pid=root_pid))
    seen = {root_pid}
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        observation = _observe(pid=pid)
        if observation is not None and str(lookalike) in observation.argv:
            return observation
        pending.extend(claude_sessions.proc_children(pid=pid))
    return None


def _await_lookalike(*, root_pid: int, lookalike: Path) -> ProcessObservation:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        observation = _lookalike_below(root_pid=root_pid, lookalike=lookalike)
        if observation is not None:
            return observation
        time.sleep(0.05)
    pytest.fail(f"the native foreground lookalike did not start within {WAIT_SECONDS}s")


def _prepared_lookalike(*, tmp_path: Path) -> tuple[Path, Path, Path]:
    prefix = tmp_path / "candidate-prefix"
    daemon_executable = runtime_prefix.ensure_runtime(
        prefix=prefix,
        install_source=str(REPO_ROOT),
    )
    assert daemon_executable is not None
    daemon_runtime = (daemon_executable.parent / "python").resolve(strict=True)
    lookalike = tmp_path / "not-overseer" / "overseerd"
    lookalike.parent.mkdir()
    lookalike.write_text(
        f"#!{daemon_runtime}\nimport time\ntime.sleep(600)\n",
        encoding="utf-8",
    )
    lookalike.chmod(0o755)
    return daemon_executable, daemon_runtime, lookalike


def _start_native_case(
    *,
    binary: str,
    socket_path: str,
    daemon_executable: Path,
    daemon_runtime: Path,
    lookalike: Path,
) -> NativeCase:
    caller = _must_tmux(
        binary=binary,
        socket_path=socket_path,
        args=["new-session", "-d", "-P", "-F", "#{pane_id}", "-s", "owned"],
    )
    candidate = _must_tmux(
        binary=binary,
        socket_path=socket_path,
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
        ],
    )
    _ = _must_tmux(
        binary=binary,
        socket_path=socket_path,
        args=["send-keys", "-t", candidate, "-l", shlex.quote(str(lookalike))],
    )
    _ = _must_tmux(
        binary=binary,
        socket_path=socket_path,
        args=["send-keys", "-t", candidate, "Enter"],
    )
    candidate_root = int(
        _must_tmux(
            binary=binary,
            socket_path=socket_path,
            args=["display-message", "-p", "-t", candidate, "#{pane_pid}"],
        )
    )
    server_pid = int(
        _must_tmux(
            binary=binary,
            socket_path=socket_path,
            args=["display-message", "-p", "-t", caller, "#{pid}"],
        )
    )
    server_starttime = claude_sessions.proc_starttime(pid=server_pid)
    assert server_starttime is not None
    caller_pid = int(
        _must_tmux(
            binary=binary,
            socket_path=socket_path,
            args=["display-message", "-p", "-t", caller, "#{pane_pid}"],
        )
    )
    return NativeCase(
        binary=binary,
        socket_path=socket_path,
        candidate_root=candidate_root,
        daemon_executable=daemon_executable,
        daemon_runtime=daemon_runtime,
        lookalike=lookalike,
        claim=terminal_ownership.OwnershipClaim(
            backend="tmux",
            socket_path=socket_path,
            server_pid=server_pid,
            server_starttime=server_starttime,
            pane_id=caller,
            pane_process_pid=caller_pid,
            distance=1,
        ),
    )


@pytest.fixture(name="native_case")
def _native_case(*, tmp_path: Path) -> Iterator[NativeCase]:
    binary = shutil.which("tmux")
    if binary is None:
        pytest.skip("tmux is unavailable")
    daemon_executable, daemon_runtime, lookalike = _prepared_lookalike(tmp_path=tmp_path)
    socket_path = str(tmp_path / "owned-tmux.sock")

    try:
        yield _start_native_case(
            binary=binary,
            socket_path=socket_path,
            daemon_executable=daemon_executable,
            daemon_runtime=daemon_runtime,
            lookalike=lookalike,
        )
    finally:
        if Path(socket_path).exists():
            _ = _tmux(binary=binary, socket_path=socket_path, args=["kill-server"])


def test_native_tmux_refuses_an_unprepared_same_runtime_overseerd_script(
    *, native_case: NativeCase
) -> None:
    first = _await_lookalike(
        root_pid=native_case.candidate_root,
        lookalike=native_case.lookalike,
    )
    second = _observe(pid=first.pid)
    assert second == first
    root_status = _status(pid=native_case.candidate_root)
    assert root_status is not None
    assert first.executable == native_case.daemon_runtime
    assert Path(first.argv[1]).resolve(strict=True) == native_case.lookalike
    assert Path(first.argv[1]).name == "overseerd"
    assert first.process_group == root_status[1]
    assert (
        tmux_daemon_liveness.foreground_daemon_process(
            root_pid=native_case.candidate_root,
            daemon_executable=native_case.daemon_executable,
        )
        is None
    )

    reading = tmux_bootstrap.TmuxBootstrap(
        daemon_executable=native_case.daemon_executable
    ).daemon_host(claim=native_case.claim)

    assert reading.pane_id == ""
    assert "not the overseer daemon with a verified exact foreground identity" in (
        reading.unresolved
    )
