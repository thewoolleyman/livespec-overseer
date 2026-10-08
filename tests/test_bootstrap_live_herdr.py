"""The two-pane bootstrap run from a REAL process inside a REAL herdr pane.

This is the native proof for `SPECIFICATION/contracts.md`'s bootstrap
preconditions and `SPECIFICATION/constraints.md`'s ownership rule, driven end to
end: a genuine `herdr --session <unique> server`, a genuine pane, a genuine
Python process running INSIDE that pane invoking the public bootstrap, and a
genuine non-editably-installed `overseerd` as the daemon it launches. Every fact
asserted afterwards is read from the SERVER'S OWN layout and process replies over
a raw socket, never from the surface under test.

The scenarios behind it are `## Scenario: The nearest verified terminal owns the
two-pane overseer` and `## Scenario: A replacement prerequisite failure preserves
every live session`.

**The invoking process is really in the pane, and that is the whole point.**
Ownership here is not staged: the in-pane process's ancestry is
`python3 -> <pane shell> -> herdr`, and the bootstrap has to walk that chain,
match the pane shell the server reports, match the server pid the socket's
`SO_PEERCRED` proves, and select THAT pane. Nothing is titled, nothing is
focus-derived, and the only environment input is the `HERDR_SOCKET_PATH` the
server itself injected — which locates a candidate endpoint and proves nothing.

**The daemon is a genuine candidate artifact, installed fresh per exercise.** A
`uv venv` plus a NON-EDITABLE `uv pip install --no-deps <this repo>` into a
uniquely owned prefix under the test's own `tmp_path`, and the assertion reads the
launched process's own `cmdline` back to confirm the running daemon came from that
exact prefix. A reused prefix could satisfy the same assertion with an older
executable, so each exercise gets its own.

**An UNRELATED sibling pane with a long-lived sentinel sits below throughout.**
Its pane id, its shell pid and its sentinel pid are recorded before the bootstrap
and re-read after, so "unrelated panes and processes survive" is a measurement
rather than an inference.

**The lost-acknowledgement case is injected AFTER the real effects.** A forwarding
AF_UNIX proxy owned by this test relays every request byte-for-byte except the
`pane.send_input` that carries the daemon launch: that one request is WITHHELD —
not forwarded, and answered with nothing, which is the client-side shape of a
committed request that goes unanswered. The split and the swap really happened, so
the created pane really exists above the original; what is lost is the answer. The
exercise then proves three things the requirement names: the outcome is uncertain
rather than failed, the launch was never re-sent, and a REPEAT bootstrap over the
real socket refuses — naming the retained shell it found rather than treating it
as a dead daemon — while splitting nothing and terminating nothing.

Session isolation is herdr's own `--session` mechanism: every session name carries
this test process's pid, and teardown stops and deletes BY THAT EXACT NAME.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from test_herdr_live_observations import (
    PANE_CWD,
    pane_ids,
    process_info_reply,
    raw_request,
    read_foreground,
    run_in_pane,
    split_pane,
    start_owned_server,
    stop_owned_server,
)

__all__: list[str] = []

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_TIMEOUT = 120.0
DAEMON_TIMEOUT = 60.0
POLL_SECONDS = 0.2
ACCEPT_POLL = 0.5
INSTALL_TIMEOUT = 600.0
SENTINEL_COMMAND = "sleep 600"
SENTINEL_NAME = "sleep"

# The in-pane driver. It builds the REAL probe, the REAL herdr bootstrap backend
# and the REAL `/proc` parent reader, so what runs in the pane is the shipped
# public path rather than a rehearsal of it. The socket override exists only for
# the fault-injection exercise, which points the whole bootstrap at this test's
# forwarding proxy; left empty, the probe reads the environment the server
# injected, exactly as a bootstrap invoked by an operator would.
_DRIVER_SOURCE = """
import json
import os
import sys

repo, out_path, command, socket_override = sys.argv[1:5]
sys.path.insert(0, os.path.join(repo, "overseer"))

import bootstrap
import claude_sessions
import herdr_bootstrap
import terminal_probes

environ = dict(os.environ)
if socket_override:
    environ["HERDR_SOCKET_PATH"] = socket_override

outcome = bootstrap.bootstrap_two_pane(
    caller=bootstrap.CallerEvidence(
        pid=os.getpid(),
        environ=environ,
        probes=(terminal_probes.HerdrOwnershipProbe(),),
        ppid_of=claude_sessions.proc_ppid,
    ),
    backends={"herdr": herdr_bootstrap.HerdrBootstrap()},
    cwd="/tmp",
    command=command,
)
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(
        {
            "ok": outcome.ok,
            "backend": outcome.backend,
            "pane_id": outcome.pane_id,
            "created": outcome.created,
            "reused": outcome.reused,
            "error": outcome.error,
            "effect_unknown": outcome.effect_unknown,
            "probe_errors": list(outcome.probe_errors),
            "invoking_pid": os.getpid(),
        },
        handle,
    )
"""


@dataclass(frozen=True, kw_only=True)
class LiveTab:
    """A live owned herdr server, the invoking pane, and one unrelated sibling."""

    session: str
    socket_path: str
    server_pid: int
    invoking: str
    sibling: str
    sibling_shell_pid: int
    sentinel_pid: int
    driver: Path
    scratch: Path


def _uv(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    """One `uv` invocation, named by its ABSOLUTE resolved path."""
    binary = shutil.which("uv")
    if binary is None:
        pytest.skip("uv is not available, so no candidate runtime can be installed")
    return subprocess.run(  # noqa: S603 — the uv CLI, not a Python child.
        [binary, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=INSTALL_TIMEOUT,
    )


def _candidate_runtime(*, prefix: Path) -> Path:
    """A genuine `overseerd` installed NON-EDITABLY into a fresh, unique prefix.

    One prefix per artifact: `runtime_prefix.ensure_runtime` short-circuits on an
    existing executable before it consults its install source, so reusing a prefix
    would let an older build satisfy a provenance assertion about this one.
    """
    venv = prefix / "venv"
    created = _uv(args=["venv", str(venv)])
    assert created.returncode == 0, created.stderr
    installed = _uv(
        args=[
            "pip",
            "install",
            "--python",
            str(venv / "bin" / "python"),
            "--no-deps",
            str(REPO_ROOT),
        ]
    )
    assert installed.returncode == 0, installed.stderr
    executable = venv / "bin" / "overseerd"
    assert executable.is_file(), f"no overseerd in the installed candidate prefix {prefix}"
    return executable


def _daemon_command(*, prefix: Path, home: Path) -> str:
    """The launch the bootstrap carries into the new pane.

    `HOME` is redirected so the daemon's own operator-home stores and its
    singleton lock land inside this exercise's scratch tree and never touch real
    host state.
    """
    home.mkdir(parents=True, exist_ok=True)
    return f"HOME={home} {_candidate_runtime(prefix=prefix)}"


def _geometry(*, socket_path: str, pane_id: str) -> tuple[dict[str, int], str]:
    """Every pane's TOP row on the tab plus the focused pane, from the REAL server."""
    reply = raw_request(socket_path=socket_path, method="pane.layout", params={"pane_id": pane_id})
    layout = reply["result"]["layout"]
    tops = {str(pane["pane_id"]): int(pane["rect"]["y"]) for pane in layout["panes"]}
    return tops, str(layout["focused_pane_id"])


def _foreground(*, socket_path: str, pane_id: str) -> Any:
    reading = read_foreground(reply=process_info_reply(socket_path=socket_path, pane_id=pane_id))
    assert reading is not None, f"no usable process reading for {pane_id!r}"
    return reading


def _await_occupant(*, socket_path: str, pane_id: str, name: str) -> int:
    """The pid of the single `name` process occupying `pane_id`'s foreground."""
    deadline = time.monotonic() + DAEMON_TIMEOUT
    seen = ""
    while time.monotonic() < deadline:
        reading = _foreground(socket_path=socket_path, pane_id=pane_id)
        named = reading.pids_named(name=name)
        if named and reading.group_id != reading.shell_pid:
            return named[0]
        seen = f"group {reading.group_id} shell {reading.shell_pid} {reading.processes}"
        time.sleep(POLL_SECONDS)
    pytest.fail(f"{name!r} never occupied {pane_id!r} within {DAEMON_TIMEOUT}s; last saw {seen}")


def _pid_alive(*, pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def _await_outcome(*, path: Path) -> dict[str, Any]:
    """The in-pane driver's recorded outcome, within the bound."""
    deadline = time.monotonic() + BOOTSTRAP_TIMEOUT
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            with path.open(encoding="utf-8") as handle:
                parsed: dict[str, Any] = json.load(handle)
            return parsed
        time.sleep(POLL_SECONDS)
    pytest.fail(f"the in-pane bootstrap never recorded an outcome at {path} ")


def _invoke(
    *, live: LiveTab, out_name: str, command: str, socket_override: str = ""
) -> dict[str, Any]:
    """Run the public bootstrap FROM the invoking pane and read back its outcome."""
    out = live.scratch / out_name
    run_in_pane(
        socket_path=live.socket_path,
        pane_id=live.invoking,
        command=(
            f"{sys.executable} {live.driver} {REPO_ROOT} {out} " f"'{command}' '{socket_override}'"
        ),
    )
    return _await_outcome(path=out)


def _write_driver(*, scratch: Path) -> Path:
    """The driver script, named by an ABSOLUTE path so the pane needs no PATH.

    The interpreter is named absolutely for the same reason: resolving `python` by
    name inside the pane would depend on whatever PATH the declared minimal shell
    produces, which is the server's choice rather than this exercise's.
    """
    driver = scratch / "bootstrap_driver.py"
    driver.write_text(_DRIVER_SOURCE, encoding="utf-8")
    return driver


@pytest.fixture(name="live_tab")
def _live_tab(*, tmp_path: Path) -> Iterator[LiveTab]:
    """One owned server, an invoking pane, and one unrelated sibling pane below it."""
    session = f"overseer-bootstrap-{os.getpid()}"
    try:
        owned = start_owned_server(session=session, scratch=tmp_path, cwd=PANE_CWD)
        sibling = split_pane(
            socket_path=owned.socket_path, pane_id=owned.root, direction="down", ratio=0.5
        )
        run_in_pane(socket_path=owned.socket_path, pane_id=sibling, command=SENTINEL_COMMAND)
        sentinel = _await_occupant(
            socket_path=owned.socket_path, pane_id=sibling, name=SENTINEL_NAME
        )
        yield LiveTab(
            session=session,
            socket_path=owned.socket_path,
            server_pid=owned.server_pid,
            invoking=owned.root,
            sibling=sibling,
            sibling_shell_pid=_foreground(socket_path=owned.socket_path, pane_id=sibling).shell_pid,
            sentinel_pid=sentinel,
            driver=_write_driver(scratch=tmp_path),
            scratch=tmp_path,
        )
    finally:
        stop_owned_server(session=session)


def _assert_placed_above(*, live: LiveTab, daemon_pane: str, before_invoking: Any) -> None:
    """Geometry and identity, read from the server rather than from the bootstrap."""
    tops, focused = _geometry(socket_path=live.socket_path, pane_id=live.invoking)
    assert tops[daemon_pane] < tops[live.invoking] < tops[live.sibling]
    assert focused == live.invoking
    after = _foreground(socket_path=live.socket_path, pane_id=live.invoking)
    assert after.shell_pid == before_invoking.shell_pid


def _assert_candidate_daemon(*, live: LiveTab, daemon_pane: str, prefix: Path) -> int:
    """One ACTUAL live daemon in the top pane, provably from the fresh prefix."""
    daemon_pid = _await_occupant(
        socket_path=live.socket_path, pane_id=daemon_pane, name="overseerd"
    )
    reading = _foreground(socket_path=live.socket_path, pane_id=daemon_pane)
    assert reading.group_id != reading.shell_pid
    assert str(prefix) in Path(f"/proc/{daemon_pid}/cmdline").read_bytes().decode(errors="replace")
    return daemon_pid


def _assert_sibling_untouched(*, live: LiveTab) -> None:
    assert (
        _foreground(socket_path=live.socket_path, pane_id=live.sibling).shell_pid
        == live.sibling_shell_pid
    )
    assert _pid_alive(pid=live.sentinel_pid)


def test_the_bootstrap_places_a_live_daemon_above_its_own_pane_and_then_reuses_it(
    *, live_tab: LiveTab
) -> None:
    """A1 and A2 natively: one daemon pane above, identity and focus kept, repeat reuses."""
    prefix = live_tab.scratch / "candidate-one"
    command = _daemon_command(prefix=prefix, home=live_tab.scratch / "daemon-home-one")
    before_invoking = _foreground(socket_path=live_tab.socket_path, pane_id=live_tab.invoking)
    before_panes = set(pane_ids(socket_path=live_tab.socket_path))

    outcome = _invoke(live=live_tab, out_name="first.json", command=command)

    assert outcome["ok"], outcome
    assert outcome["backend"] == "herdr"
    assert outcome["created"] is True
    assert outcome["reused"] is False
    daemon_pane = outcome["pane_id"]
    assert daemon_pane not in before_panes

    _assert_placed_above(live=live_tab, daemon_pane=daemon_pane, before_invoking=before_invoking)
    daemon_pid = _assert_candidate_daemon(live=live_tab, daemon_pane=daemon_pane, prefix=prefix)
    _assert_sibling_untouched(live=live_tab)

    repeat = _invoke(live=live_tab, out_name="second.json", command=command)

    assert repeat["ok"], repeat
    assert repeat["reused"] is True
    assert repeat["created"] is False
    assert repeat["pane_id"] == daemon_pane
    # No third pane, and the same daemon process: the repeat split nothing and
    # launched nothing.
    assert set(pane_ids(socket_path=live_tab.socket_path)) == before_panes | {daemon_pane}
    assert _pid_alive(pid=daemon_pid)
    assert _pid_alive(pid=live_tab.sentinel_pid)


@dataclass(kw_only=True)
class ProxyState:
    """What the forwarding proxy relayed, and the one fault it injected."""

    requests: list[dict[str, Any]] = field(default_factory=list)
    created: str = ""
    withheld: int = 0

    def methods(self) -> list[str]:
        return [str(request["method"]) for request in self.requests]


def _read_frame(*, conn: socket.socket) -> bytes | None:
    buffered = b""
    while not buffered.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        buffered += chunk
    return buffered or None


def _forward(*, socket_path: str, raw: bytes) -> bytes:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(raw)
    try:
        return _read_frame(conn=sock) or b""
    finally:
        sock.close()


def _serve_proxy(*, listener: socket.socket, real_socket: str, state: ProxyState) -> None:
    """Relay verbatim, WITHHOLDING only the request that carries the daemon launch.

    An idle `accept` is not a shutdown: `socket.timeout` is an `OSError` subclass,
    so a bare `except OSError: return` would end this thread during the quiet
    interval while the in-pane driver is still starting. Only a genuine closure —
    this fixture's own teardown — ends the loop.
    """
    listener.settimeout(ACCEPT_POLL)
    while True:
        try:
            conn, _peer = listener.accept()
        except TimeoutError:
            continue
        except OSError:
            return
        with conn:
            raw = _read_frame(conn=conn)
            if raw is None:
                continue
            request = json.loads(raw)
            state.requests.append(request)
            if request["method"] == "pane.send_input" and "keys" in request["params"]:
                # The launch. Neither forwarded nor answered: the pane stays a
                # retained shell and the caller cannot tell whether it does.
                state.withheld += 1
                continue
            answered = _forward(socket_path=real_socket, raw=raw)
            if request["method"] == "pane.split" and answered:
                reply = json.loads(answered.split(b"\n")[0])
                state.created = str(reply["result"]["pane"]["pane_id"])
            with contextlib.suppress(OSError):
                conn.sendall(answered)


@dataclass(kw_only=True)
class OwnedProxy:
    """The listener and relay thread this fixture opened, so it can close them."""

    listener: socket.socket
    thread: threading.Thread
    state: ProxyState
    path: str

    def shut_down(self) -> None:
        with contextlib.suppress(OSError):
            self.listener.close()
        self.thread.join(timeout=ACCEPT_POLL * 10)


@pytest.fixture(name="withholding_proxy")
def _withholding_proxy(*, live_tab: LiveTab) -> Iterator[OwnedProxy]:
    path = str(live_tab.scratch / "withhold.sock")
    state = ProxyState()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(16)
    thread = threading.Thread(
        target=_serve_proxy,
        kwargs={"listener": listener, "real_socket": live_tab.socket_path, "state": state},
        daemon=True,
    )
    thread.start()
    owned = OwnedProxy(listener=listener, thread=thread, state=state, path=path)
    try:
        yield owned
    finally:
        owned.shut_down()


def test_a_withheld_launch_answer_stays_unresolved_and_is_never_repeated_or_cleaned_up(
    *, live_tab: LiveTab, withholding_proxy: OwnedProxy
) -> None:
    """A6 natively: the split really landed, its launch answer did not, nothing is redone."""
    prefix = live_tab.scratch / "candidate-two"
    command = _daemon_command(prefix=prefix, home=live_tab.scratch / "daemon-home-two")
    before_panes = set(pane_ids(socket_path=live_tab.socket_path))

    outcome = _invoke(
        live=live_tab,
        out_name="withheld.json",
        command=command,
        socket_override=withholding_proxy.path,
    )

    assert not outcome["ok"]
    # Uncertain, not failed: the request was committed and went unanswered.
    assert outcome["effect_unknown"] is True
    created = outcome["pane_id"]
    assert created == withholding_proxy.state.created != ""
    assert withholding_proxy.state.withheld == 1
    assert withholding_proxy.state.methods().count("pane.split") == 1

    # The REAL server shows the split landed: the created pane exists, above the
    # invoking pane, holding its own retained shell and no daemon.
    live_panes = set(pane_ids(socket_path=live_tab.socket_path))
    assert live_panes == before_panes | {created}
    tops, focused = _geometry(socket_path=live_tab.socket_path, pane_id=live_tab.invoking)
    assert tops[created] < tops[live_tab.invoking]
    assert focused == live_tab.invoking
    stranded = _foreground(socket_path=live_tab.socket_path, pane_id=created)
    assert stranded.group_id == stranded.shell_pid

    repeat = _invoke(live=live_tab, out_name="withheld-repeat.json", command=command)

    # The repeat refuses on fresh evidence, splits nothing, and kills nothing.
    assert not repeat["ok"]
    assert repeat["created"] is False
    assert repeat["reused"] is False
    assert "retained shell" in repeat["error"]
    assert set(pane_ids(socket_path=live_tab.socket_path)) == live_panes
    assert (
        _foreground(socket_path=live_tab.socket_path, pane_id=created).shell_pid
        == stranded.shell_pid
    )
    assert _pid_alive(pid=stranded.shell_pid)
    assert _pid_alive(pid=live_tab.sentinel_pid)
