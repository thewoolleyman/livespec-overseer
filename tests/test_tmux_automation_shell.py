"""The shared tmux session builder marks automation-owned shells."""

from __future__ import annotations

import ast
import os
import shutil
import time
from pathlib import Path

from test_tmuxio_fakes import io as _io

from overseer import tmux_process, tmuxio

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCANNED_DIRS = (
    _REPO_ROOT / "overseer",
    _REPO_ROOT / ".claude-plugin" / "overseer",
    _REPO_ROOT / "tests",
    _REPO_ROOT / "scripts",
)
_NEW_SESSION = "new-session"
_MARKER = b"LIVESPEC_AUTOMATION_SHELL=1"
# A guard on an EVENT wait (the pane process leaving the tmux image), never a
# sleep the verdict depends on.
_EXEC_GUARD_SECONDS = 30.0


def _literal_new_session_calls(*, path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(
            isinstance(part, ast.Constant) and part.value == _NEW_SESSION
            for argument in [
                *node.args,
                *(keyword.value for keyword in node.keywords if keyword.arg in {"args", "argv"}),
            ]
            for part in ast.walk(argument)
        )
    ]


def test_overseer_new_session_argv_marks_the_automation_shell() -> None:
    io, fake = _io()

    assert io.new_session(name="livespec:t", cwd="/data/projects/livespec") is True
    assert fake.calls[0]["argv"] == [
        "tmux",
        "new-session",
        "-e",
        "LIVESPEC_AUTOMATION_SHELL=1",
        "-d",
        "-s",
        "livespec:t",
        "-c",
        "/data/projects/livespec",
    ]


def test_no_tmux_session_creation_bypasses_the_shared_builder() -> None:
    bypasses = [
        f"{path.relative_to(_REPO_ROOT)}:{line}"
        for root in _SCANNED_DIRS
        for path in root.rglob("*.py")
        for line in _literal_new_session_calls(path=path)
    ]

    assert bypasses == [], "tmux new-session must use tmuxio.new_session_args:\n" + "\n".join(
        bypasses
    )


def test_live_tmux_pane_inherits_the_automation_shell_marker(*, tmp_path: Path) -> None:
    tmux_binary = shutil.which("tmux")
    assert tmux_binary is not None, "live automation-shell coverage requires tmux"
    session = "livespec-automation-shell-test"
    run = tmux_process.SocketScopedRun(socket_path=str(tmp_path / "automation-shell.tmux"))
    io = tmuxio.TmuxIO(tmux_bin=tmux_binary, run=run)

    try:
        assert io.new_session(name=session, cwd=str(tmp_path)) is True
        pane_pid = io.pane_pid(session=session)
        assert pane_pid is not None
        _wait_until_exec_left_tmux(pid=pane_pid, tmux_binary=tmux_binary)
        environment = Path(f"/proc/{pane_pid}/environ").read_bytes().split(b"\0")
        # Assert on a boolean, never on the list: pytest renders a failing
        # `in` against the whole environment, and in a factory sandbox that
        # environment carries credentials (overseer-uzvcbn.13).
        marked = _MARKER in environment
        assert marked, f"pane process {pane_pid} lacks {_MARKER.decode()}"
    finally:
        io.kill_session(session=session)


def _wait_until_exec_left_tmux(*, pid: int, tmux_binary: str) -> None:
    """Wait until the pane process is no longer the tmux server's forked child.

    `/proc/<pid>/environ` is fixed at exec. Between tmux forking the pane and
    the shell exec'ing, the child still runs the tmux image and still carries
    the SERVER's environment, without the `-e` marker; under host load the
    read used to land in that window (run 01M6ERYRS3AZ, overseer-uzvcbn.13).
    Leaving the tmux image is the observed exec, so the marker check that
    follows reads the shell's own environment and still fails if
    `new_session` does not set the marker.
    """
    tmux_image = os.path.realpath(tmux_binary)
    deadline = time.monotonic() + _EXEC_GUARD_SECONDS
    while os.path.realpath(f"/proc/{pid}/exe") == tmux_image:
        # COVERAGE-EXEMPT: entered only when the read beats the exec, which a
        # loaded host does and an idle one usually does not.
        assert time.monotonic() < deadline, (  # pragma: no cover
            f"pane process {pid} never exec'd out of tmux"
        )
        time.sleep(0.01)  # pragma: no cover
