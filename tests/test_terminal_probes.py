"""Enumerating the panes each supported terminal INSTANCE owns, generation and all.

`terminal_ownership` decides who owns the invoking process; this is the surface
that supplies it with facts. `SPECIFICATION/constraints.md` requires instance
identity to include the live server GENERATION — proven by its process identity
and start time, because a socket path alone is reusable across a restart — and
requires an unqualified legacy tmux value to keep meaning tmux rather than being
reinterpreted. Both are graded here.

The scenario behind the tmux half is `## Scenario: Backend-qualified coordinates
preserve legacy tmux ownership`.

**Two tiers, and each one answers what the other cannot.** The hermetic cases
drive refusals a live server will not produce on request: a `list-panes` that
exits non-zero, a reply whose rows disagree about which server answered, a server
whose `/proc` start time has gone unreadable, and a pane whose process reading
fails. The NATIVE cases run a real `tmux -S <socket>` server and a real
`herdr --session <unique> server` and assert the probe's enumeration against each
server's OWN account of its panes — read over a raw socket for herdr and through
a separate `list-panes` for tmux, so the evidence never comes from the surface
under test.

Session isolation: the tmux server lives on a private socket under the test's own
`tmp_path` and is killed by that exact socket; the herdr session name carries this
test process's pid and teardown stops and deletes BY THAT EXACT NAME.
"""

from __future__ import annotations

import os
import subprocess
import time
import types
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import claude_sessions
import pytest
from test_herdr_live_observations import (
    PANE_CWD,
    pane_ids,
    process_info_reply,
    read_foreground,
    split_pane,
    start_owned_server,
    stop_owned_server,
)

from overseer import terminal_probes

__all__: list[str] = []

TMUX_BINARY = "tmux"
TMUX_READY_TIMEOUT = 15.0
POLL_SECONDS = 0.1
SERVER_PID = 4242
SERVER_STARTTIME = "99887766"
NAMED_SOCKET = "/run/user/1000/tmux-named/socket"


@dataclass(kw_only=True)
class RecordingRun:
    """Stands in for `subprocess.run`, recording argv and returning a canned result.

    `timeout` is recorded rather than ignored for the same reason `tmuxio`'s own
    double records it: a tmux that never exits is the one failure a fail-soft
    posture cannot address, so every call must carry a bound and a double that
    swallowed the kwarg could not prove it.
    """

    stdout: str = ""
    returncode: int = 0
    raises: BaseException | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        check: bool | None = None,
        timeout: float | None = None,
    ) -> Any:
        del input, capture_output, text, check
        self.calls.append({"argv": list(argv), "timeout": timeout})
        if self.raises is not None:
            raise self.raises
        return types.SimpleNamespace(returncode=self.returncode, stdout=self.stdout, stderr="")


def _starttime_reader(*, starttimes: dict[int, str | None]):
    def read(*, pid: int) -> str | None:
        return starttimes.get(pid)

    return read


def _tmux_probe(
    *,
    stdout: str = "",
    returncode: int = 0,
    raises: BaseException | None = None,
    starttimes: dict[int, str | None] | None = None,
) -> tuple[terminal_probes.TmuxOwnershipProbe, RecordingRun]:
    run = RecordingRun(stdout=stdout, returncode=returncode, raises=raises)
    probe = terminal_probes.TmuxOwnershipProbe(
        run=run,
        starttime_of=_starttime_reader(
            starttimes={SERVER_PID: SERVER_STARTTIME} if starttimes is None else starttimes
        ),
    )
    return probe, run


def _row(*, pane_id: str, pane_pid: int, server_pid: int = SERVER_PID) -> str:
    return f"{pane_id}\t{pane_pid}\t{server_pid}"


# --------------------------------------------------------------- tmux, hermetic


def test_the_default_tmux_endpoint_is_addressed_with_no_socket_argument() -> None:
    """Legacy semantics: an unqualified tmux instance is the DEFAULT server."""
    probe, run = _tmux_probe(stdout=_row(pane_id="%3", pane_pid=701) + "\n")

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.error == ""
    assert run.calls[0]["argv"][:2] == [TMUX_BINARY, "list-panes"]
    assert "-S" not in run.calls[0]["argv"]
    assert run.calls[0]["timeout"] == terminal_probes.TMUX_TIMEOUT_SECONDS


def test_a_named_tmux_endpoint_is_addressed_with_its_own_socket() -> None:
    """A named instance is retained by its socket, not by whichever server answers."""
    probe, run = _tmux_probe(stdout=_row(pane_id="%3", pane_pid=701) + "\n")

    reading = probe.owned_panes(endpoint=NAMED_SOCKET)

    assert reading.error == ""
    assert run.calls[0]["argv"][:4] == [TMUX_BINARY, "-S", NAMED_SOCKET, "list-panes"]
    assert reading.panes[0].socket_path == NAMED_SOCKET


def test_the_tmux_endpoints_are_the_default_server_plus_the_one_the_environment_names() -> None:
    probe, _ = _tmux_probe()

    endpoints = probe.endpoints(environ={terminal_probes.TMUX_ENV: f"{NAMED_SOCKET},123,0"})

    assert endpoints == (terminal_probes.DEFAULT_TMUX_ENDPOINT, NAMED_SOCKET)


def test_an_absent_or_unparseable_tmux_environment_still_probes_the_default_server() -> None:
    probe, _ = _tmux_probe()

    assert probe.endpoints(environ={}) == (terminal_probes.DEFAULT_TMUX_ENDPOINT,)
    assert probe.endpoints(environ={terminal_probes.TMUX_ENV: ""}) == (
        terminal_probes.DEFAULT_TMUX_ENDPOINT,
    )


def test_a_tmux_environment_naming_the_default_socket_is_not_probed_twice() -> None:
    probe, _ = _tmux_probe()

    endpoints = probe.endpoints(environ={terminal_probes.TMUX_ENV: ","})

    assert endpoints == (terminal_probes.DEFAULT_TMUX_ENDPOINT,)


def test_each_tmux_pane_carries_its_own_root_process_and_the_shared_generation() -> None:
    probe, _ = _tmux_probe(
        stdout=_row(pane_id="%3", pane_pid=701) + "\n" + _row(pane_id="%4", pane_pid=702) + "\n"
    )

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.error == ""
    assert [pane.pane_id for pane in reading.panes] == ["%3", "%4"]
    assert [pane.pane_process_pids for pane in reading.panes] == [(701,), (702,)]
    assert {pane.server_pid for pane in reading.panes} == {SERVER_PID}
    assert {pane.server_starttime for pane in reading.panes} == {SERVER_STARTTIME}
    assert {pane.backend for pane in reading.panes} == {"tmux"}


def test_a_tmux_server_whose_generation_is_unreadable_is_refused() -> None:
    """A pid with no `/proc` start time cannot be pinned, so it names no instance."""
    probe, _ = _tmux_probe(
        stdout=_row(pane_id="%3", pane_pid=701) + "\n", starttimes={SERVER_PID: None}
    )

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "generation is unreadable" in reading.error
    assert str(SERVER_PID) in reading.error


def test_a_failing_tmux_listing_is_a_named_refusal_rather_than_an_empty_answer() -> None:
    probe, _ = _tmux_probe(returncode=1)

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "did not answer" in reading.error


def test_a_tmux_binary_that_cannot_be_spawned_is_a_named_refusal() -> None:
    probe, _ = _tmux_probe(raises=OSError("no such file"))

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "could not be run" in reading.error


def test_a_tmux_listing_that_hangs_past_its_bound_is_a_named_refusal() -> None:
    probe, _ = _tmux_probe(raises=subprocess.TimeoutExpired(cmd="tmux", timeout=1.0))

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "could not be run" in reading.error


def test_a_malformed_tmux_row_refuses_the_whole_listing() -> None:
    """A listing that cannot be read in full is unreadable, not partially true."""
    probe, _ = _tmux_probe(stdout=_row(pane_id="%3", pane_pid=701) + "\nnot-a-row\n")

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "unreadable" in reading.error


def test_a_tmux_row_with_a_non_numeric_pid_refuses_the_whole_listing() -> None:
    probe, _ = _tmux_probe(stdout="%3\tnot-a-pid\t4242\n")

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "unreadable" in reading.error


def test_rows_disagreeing_about_which_server_answered_refuse_the_listing() -> None:
    """One socket is one server; two answers on it cannot both name this instance."""
    probe, _ = _tmux_probe(
        stdout=_row(pane_id="%3", pane_pid=701)
        + "\n"
        + _row(pane_id="%4", pane_pid=702, server_pid=9999)
        + "\n"
    )

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert "distinct server" in reading.error


def test_a_tmux_server_holding_no_panes_answers_with_no_panes_and_no_error() -> None:
    probe, _ = _tmux_probe(stdout="\n")

    reading = probe.owned_panes(endpoint=terminal_probes.DEFAULT_TMUX_ENDPOINT)

    assert reading.panes == ()
    assert reading.error == ""


def test_the_socket_scoped_runner_binds_every_call_to_one_named_server() -> None:
    """The retention mechanism: a selected named instance keeps being addressed."""
    inner = RecordingRun(stdout="ok")
    scoped = terminal_probes.SocketScopedRun(socket_path=NAMED_SOCKET, run=inner)

    completed = scoped(
        [TMUX_BINARY, "capture-pane", "-p"], input=None, capture_output=True, text=True, timeout=3.0
    )

    assert completed.stdout == "ok"
    assert inner.calls[0]["argv"] == [
        TMUX_BINARY,
        "-S",
        NAMED_SOCKET,
        "capture-pane",
        "-p",
    ]
    assert inner.calls[0]["timeout"] == 3.0


# -------------------------------------------------------------- herdr, hermetic


@dataclass(frozen=True, kw_only=True)
class FakePaneRow:
    pane_id: str


@dataclass(frozen=True, kw_only=True)
class FakeProcess:
    pane_id: str
    shell_pid: int
    process_group_id: int


@dataclass(kw_only=True)
class FakeHerdrAdapter:
    """A scripted stand-in for the herdr observation surface."""

    peer: Any = None
    identify_error: str = ""
    pane_rows: tuple[FakePaneRow, ...] = ()
    listing_error: str = ""
    processes: dict[str, FakeProcess] = field(default_factory=dict)
    process_errors: dict[str, str] = field(default_factory=dict)
    targets: list[Any] = field(default_factory=list)

    def identify(self, *, socket_path: str) -> Any:
        del socket_path
        return types.SimpleNamespace(
            ok=not self.identify_error, peer=self.peer, error=self.identify_error
        )

    def list_panes(self, *, target: Any) -> Any:
        self.targets.append(target)
        return types.SimpleNamespace(
            ok=not self.listing_error, panes=self.pane_rows, error=self.listing_error
        )

    def foreground(self, *, target: Any) -> Any:
        self.targets.append(target)
        error = self.process_errors.get(target.pane_id, "")
        if error:
            return types.SimpleNamespace(ok=False, process=None, error=error)
        return types.SimpleNamespace(ok=True, process=self.processes.get(target.pane_id), error="")


def _peer() -> Any:
    return types.SimpleNamespace(pid=SERVER_PID, uid=os.getuid(), starttime=SERVER_STARTTIME)


def test_the_herdr_endpoints_are_the_default_socket_plus_the_one_the_environment_names(
    *, tmp_path: Path
) -> None:
    probe = terminal_probes.HerdrOwnershipProbe(adapter=FakeHerdrAdapter(), home=tmp_path)

    endpoints = probe.endpoints(
        environ={terminal_probes.HERDR_SOCKET_ENV: "/run/user/1000/named/herdr.sock"}
    )

    assert endpoints == (
        str(tmp_path / ".config" / "herdr" / "herdr.sock"),
        "/run/user/1000/named/herdr.sock",
    )


def test_a_herdr_environment_naming_the_default_socket_is_not_probed_twice(
    *, tmp_path: Path
) -> None:
    default = str(tmp_path / ".config" / "herdr" / "herdr.sock")
    probe = terminal_probes.HerdrOwnershipProbe(adapter=FakeHerdrAdapter(), home=tmp_path)

    assert probe.endpoints(environ={terminal_probes.HERDR_SOCKET_ENV: default}) == (default,)
    assert probe.endpoints(environ={}) == (default,)


def test_each_herdr_pane_offers_its_retained_shell_and_its_foreground_leader() -> None:
    adapter = FakeHerdrAdapter(
        peer=_peer(),
        pane_rows=(FakePaneRow(pane_id="w1:p1"), FakePaneRow(pane_id="w1:p2")),
        processes={
            "w1:p1": FakeProcess(pane_id="w1:p1", shell_pid=801, process_group_id=815),
            "w1:p2": FakeProcess(pane_id="w1:p2", shell_pid=802, process_group_id=802),
        },
    )
    probe = terminal_probes.HerdrOwnershipProbe(adapter=adapter)

    reading = probe.owned_panes(endpoint="/run/user/1000/herdr.sock")

    assert reading.error == ""
    assert [pane.pane_id for pane in reading.panes] == ["w1:p1", "w1:p2"]
    assert reading.panes[0].pane_process_pids == (801, 815)
    # An idle pane reports its shell as the foreground leader; the same pid twice
    # is one candidate, not two.
    assert reading.panes[1].pane_process_pids == (802,)
    assert {pane.server_pid for pane in reading.panes} == {SERVER_PID}
    assert {pane.server_starttime for pane in reading.panes} == {SERVER_STARTTIME}
    assert {pane.backend for pane in reading.panes} == {"herdr"}


def test_a_herdr_instance_that_cannot_be_identified_names_no_panes() -> None:
    probe = terminal_probes.HerdrOwnershipProbe(
        adapter=FakeHerdrAdapter(identify_error="socket is unreachable")
    )

    reading = probe.owned_panes(endpoint="/run/user/1000/herdr.sock")

    assert reading.panes == ()
    assert "socket is unreachable" in reading.error


def test_a_herdr_instance_identified_without_a_generation_names_no_panes() -> None:
    """An `ok` identification carrying no peer proves no generation; fail closed."""
    probe = terminal_probes.HerdrOwnershipProbe(adapter=FakeHerdrAdapter(peer=None))

    reading = probe.owned_panes(endpoint="/run/user/1000/herdr.sock")

    assert reading.panes == ()
    assert "generation" in reading.error


def test_an_unreadable_herdr_pane_listing_is_a_named_refusal() -> None:
    probe = terminal_probes.HerdrOwnershipProbe(
        adapter=FakeHerdrAdapter(peer=_peer(), listing_error="pane listing is unreadable")
    )

    reading = probe.owned_panes(endpoint="/run/user/1000/herdr.sock")

    assert reading.panes == ()
    assert "pane listing is unreadable" in reading.error


def test_one_unreadable_pane_process_refuses_the_whole_instance() -> None:
    """Fail closed and NAME the pane: a skipped pane would read as 'does not own us'."""
    adapter = FakeHerdrAdapter(
        peer=_peer(),
        pane_rows=(FakePaneRow(pane_id="w1:p1"), FakePaneRow(pane_id="w1:p2")),
        processes={"w1:p1": FakeProcess(pane_id="w1:p1", shell_pid=801, process_group_id=801)},
        process_errors={"w1:p2": "process info reply carried an unreadable payload"},
    )
    probe = terminal_probes.HerdrOwnershipProbe(adapter=adapter)

    reading = probe.owned_panes(endpoint="/run/user/1000/herdr.sock")

    assert reading.panes == ()
    assert "w1:p2" in reading.error
    assert "unreadable payload" in reading.error


def test_every_herdr_request_carries_the_identified_generation() -> None:
    """The pane reads are addressed to the generation identification returned."""
    adapter = FakeHerdrAdapter(
        peer=_peer(),
        pane_rows=(FakePaneRow(pane_id="w1:p1"),),
        processes={"w1:p1": FakeProcess(pane_id="w1:p1", shell_pid=801, process_group_id=801)},
    )
    probe = terminal_probes.HerdrOwnershipProbe(adapter=adapter)

    _ = probe.owned_panes(endpoint="/run/user/1000/herdr.sock")

    assert [target.pane_id for target in adapter.targets] == ["", "w1:p1"]
    assert {target.server_pid for target in adapter.targets} == {SERVER_PID}
    assert {target.server_starttime for target in adapter.targets} == {SERVER_STARTTIME}
    assert {target.socket_path for target in adapter.targets} == {"/run/user/1000/herdr.sock"}


# ----------------------------------------------------------------------- native


def _tmux_available() -> bool:
    try:
        completed = subprocess.run(  # noqa: S603 — the tmux CLI, not a Python child.
            [TMUX_BINARY, "-V"], capture_output=True, text=True, check=False, timeout=10.0
        )
    except OSError:
        return False
    return completed.returncode == 0


def _tmux(*, socket_path: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the tmux CLI, not a Python child.
        [TMUX_BINARY, "-S", socket_path, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15.0,
    )


@pytest.fixture(name="live_tmux_socket")
def _live_tmux_socket(*, tmp_path: Path) -> Iterator[str]:
    """One real tmux server on a private socket, killed by that exact socket."""
    if not _tmux_available():
        pytest.skip("tmux is not available on this host")
    socket_path = str(tmp_path / "tmux.sock")
    started = _tmux(
        socket_path=socket_path,
        args=["new-session", "-d", "-s", "probe-native", "-c", PANE_CWD, "sleep 300"],
    )
    assert started.returncode == 0, started.stderr
    try:
        deadline = time.monotonic() + TMUX_READY_TIMEOUT
        while time.monotonic() < deadline:
            if _tmux(socket_path=socket_path, args=["list-panes", "-a"]).returncode == 0:
                break
            time.sleep(POLL_SECONDS)
        yield socket_path
    finally:
        _ = _tmux(socket_path=socket_path, args=["kill-server"])


def test_a_real_tmux_server_is_enumerated_with_its_real_generation(
    *, live_tmux_socket: str
) -> None:
    """The probe's account of a live instance matches the server's own, pid-for-pid."""
    control = _tmux(
        socket_path=live_tmux_socket,
        args=["list-panes", "-a", "-F", "#{pane_id} #{pane_pid} #{pid}"],
    )
    assert control.returncode == 0, control.stderr
    expected = [line.split() for line in control.stdout.splitlines() if line.strip()]

    reading = terminal_probes.TmuxOwnershipProbe().owned_panes(endpoint=live_tmux_socket)

    assert reading.error == ""
    assert [
        [pane.pane_id, str(pane.pane_process_pids[0]), str(pane.server_pid)]
        for pane in reading.panes
    ] == expected
    server_pid = reading.panes[0].server_pid
    assert reading.panes[0].server_starttime == claude_sessions.proc_starttime(pid=server_pid)
    assert reading.panes[0].socket_path == live_tmux_socket


def test_a_real_herdr_server_is_enumerated_with_its_real_generation(*, tmp_path: Path) -> None:
    """Every enumerated pane process is the one the real server reports for it."""
    session = f"overseer-probes-{os.getpid()}"
    try:
        owned = start_owned_server(session=session, scratch=tmp_path)
        second = split_pane(socket_path=owned.socket_path, pane_id=owned.root, direction="down")
        live = sorted(pane_ids(socket_path=owned.socket_path))
        assert live == sorted([owned.root, second])

        reading = terminal_probes.HerdrOwnershipProbe().owned_panes(endpoint=owned.socket_path)

        assert reading.error == ""
        assert sorted(pane.pane_id for pane in reading.panes) == live
        assert {pane.server_pid for pane in reading.panes} == {owned.server_pid}
        assert {pane.server_starttime for pane in reading.panes} == {
            claude_sessions.proc_starttime(pid=owned.server_pid)
        }
        for pane in reading.panes:
            control = read_foreground(
                reply=process_info_reply(socket_path=owned.socket_path, pane_id=pane.pane_id)
            )
            assert control is not None, f"no usable process reading for {pane.pane_id!r}"
            assert control.shell_pid in pane.pane_process_pids
    finally:
        stop_owned_server(session=session)
