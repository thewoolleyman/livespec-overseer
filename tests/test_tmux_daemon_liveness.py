"""Deterministic companion coverage for tmux retained-shell daemon evidence.

The frozen native regression proves the behavior through public
``overseer-start``.  These cases keep the bounded process walk and its fail-closed
edges gradeable on hosts without a native tmux/Herdr nesting setup; they are
postimplementation companion coverage, not a reconstructed Red receipt.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from overseer import terminal_ownership, tmux_bootstrap, tmux_daemon_liveness

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
