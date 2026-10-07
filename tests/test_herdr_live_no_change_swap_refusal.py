"""A declined swap against live herdr: real split, real decline, nothing written.

The native counterpart of `tests/test_herdr_layout_no_change_swap_refusal.py`,
carrying both controls the deterministic file cannot: a REAL pane that really was
created and really was not moved, and — in the same harness, through the same
proxy — the happy path still completing.

**The fault injection, stated plainly, including what it does NOT reproduce.**
The writer talks to a forwarding AF_UNIX proxy owned by this test process with a
real `herdr --session <unique> server` behind it. Every request is relayed
byte-for-byte except one: the `pane.swap` request is NOT forwarded, and the proxy
answers it itself with `{"changed": false, "reason": "cross_tab", ...}` echoing
exactly the two panes the request named. So the decline is injected, while
everything it is a decline OF is real — the pane was really split into existence
by the real server, and really was not moved, which the test then confirms by
reading the real geometry.

The decline is injected rather than provoked because it CANNOT be provoked
through this adapter: herdr answers `changed: false` for a cross-tab or
same-pane swap, and the sequence refuses both of those earlier — a pane in
another tab fails the tab-membership proof, and an acknowledgement naming the
original pane fails the newness proof. A real server declining a swap the
adapter is willing to ask for is therefore not reachable from here, and the
injected reply is the measured shape of that answer, not an invented one.

What the assertions then establish is not the reply — it is the WORLD the reply
describes: the created pane exists, sits below the target, still holds its own
idle shell, and received nothing. That is a known partial layout, which is why
the outcome reports it as certain while still naming the pane.

The clean control runs the identical harness with no fault at all, so "the
refusal is caused by the decline" is a measurement rather than an assumption —
a gate that refused everything would pass the first test and fail the second.

**THE CLEAN CONTROL HAD NO READINESS PRECONDITION AT ALL, AND THAT IS WHAT THIS
FILE WAS REPAIRED FOR (work-item `overseer-dihsef`).** The pane the command goes
into is created BY the adapter and read three round trips later, so nothing this
fixture does beforehand can say anything about what is in its foreground at that
instant. On the operator host a freshly created pane's `zsh` forks `mise` and
`atuin` while starting, so the adapter's pre-launch reading finds the pane
OCCUPIED and legitimately refuses — and the clean control, whose whole job is to
assert that the happy path completes, failed. Measured on the host postmerge gate
`20261007T050721Z-3567360`: `check-coverage` red, and a two-node diagnostic then
reported the clean control refusing with foreground group 87165 against retained
shell 87152.

The same shape was then staged deliberately in the factory sandbox before this
file was touched, which is what makes the premise a measurement rather than a
reading of the host log: with one real `sleep 300` observed owning the created
pane `w1:p2` (child 5786 under retained shell 5778), the shipped clean control's
own `assert outcome.ok is True` failed with
`'w1:p2' is OCCUPIED: foreground group 5786 is not its retained shell 5778`.

So `_split_top` now runs the real sequence through `ReadyShellGate`, which stages
one real bounded child in that exact pane, OBSERVES it, waits for it to exit and
for the SAME pinned retained shell to own its foreground again, and only then
lets the adapter take its own reading. A gate that cannot establish that fails
the exercise BY NAME — it is never reported as the adapter declining to launch.
The staged child is a bounded DISCRIMINATING instance of a non-idle created pane,
not a reproduction of the operator's `zsh` startup; a login shell that loads
nothing — which this sandbox has — was ready anyway, so the pass recorded here is
a preservation control over a guard that already held.
`tests/test_herdr_live_observations.py` carries that framing in full.

**The proxy has to SURVIVE that establishment window, and it did not.** The
establishment talks to the real server directly, so the proxy's listener sits
idle throughout it — and `socket.timeout` is an `OSError` subclass, so the old
`except OSError: return` treated an ordinary idle accept as a shutdown and killed
the relay thread mid-sequence. A timeout is now distinguished from a real
closure, and teardown closes exactly the listeners this fixture opened and joins
their threads, so the loop ends because this file ended it.

Session isolation is herdr's own `--session` mechanism: the name carries this
test process's pid, and teardown stops and deletes BY THAT EXACT NAME.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    BoundedPoll,
    ForegroundReading,
    ReadyShellGate,
    await_occupying_child,
    parent_pid_of,
    process_info_reply,
    read_foreground,
    startup_transient,
)

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
# A liveness floor, not a latency budget. This was briefly raised to 120.0 on a
# diagnosis that did not hold up — the clean control's failures were traced to
# its wait PREDICATE, not to this bound, so the raise is backed out rather than
# left behind as a fix for something else. The predicate itself is now a
# delivered helper (`await_occupying_child`); see `_launched_child`.
LAUNCH_TIMEOUT = 20.0
# Short enough that teardown closing a listener ends its relay thread promptly,
# long enough that the loop is not spinning. The establishment window this has to
# survive is seconds of real waiting with no connection arriving.
ACCEPT_POLL = 0.5
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
DECLINE_REASON = "cross_tab"
MARKER = "OVNOCHANGE1"
DAEMON_COMMAND = f"sleep 120 #{MARKER}"
LAUNCH_NAME = "sleep"


@dataclass(kw_only=True)
class ProxyState:
    """What the proxy relayed, and whether it answered the swap itself."""

    decline: bool
    created: str = ""
    declined: bool = False
    requests: list[dict[str, Any]] = field(default_factory=list)

    def methods(self) -> list[str]:
        return [str(request["method"]) for request in self.requests]

    def writes(self) -> list[str]:
        """Every pane the WRITER sent input to — this fixture's own setup excluded.

        The readiness gate delivers its controlled child over a separate raw
        connection to the REAL server, which never passes through this listener,
        so everything recorded here was written by the surface under test. That
        separation is the whole reason the gate is pointed at the real socket
        rather than at the proxy.
        """
        return [
            str(request["params"].get("pane_id"))
            for request in self.requests
            if request["method"] == "pane.send_input"
        ]


@dataclass(frozen=True, kw_only=True)
class LiveProxiedTab:
    """A real herdr tab plus the proxy the writer is pointed at."""

    real_socket: str
    proxy_socket: str
    original: str
    unrelated: str
    transient: str
    state: ProxyState


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _read_frame(*, conn: socket.socket) -> bytes | None:
    buffered = b""
    while not buffered.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        buffered += chunk
    return buffered or None


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw round trip to the REAL server, for setup and for control facts."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(json.dumps({"id": "fixture", "method": method, "params": params}).encode() + b"\n")
    try:
        answered = _read_frame(conn=sock)
    finally:
        sock.close()
    parsed: dict[str, Any] = json.loads((answered or b"{}").split(b"\n")[0])
    return parsed


def _geometry(*, socket_path: str, pane_id: str) -> dict[str, int]:
    reply = _raw_request(socket_path=socket_path, method="pane.layout", params={"pane_id": pane_id})
    return {
        str(pane["pane_id"]): int(pane["rect"]["y"]) for pane in reply["result"]["layout"]["panes"]
    }


def _reading(*, socket_path: str, pane_id: str) -> ForegroundReading:
    """`pane_id`'s live process reading, or an explicit FIXTURE failure.

    Control evidence comes from the real server over a raw socket, never from the
    surface under test, and an unusable reply stops the exercise here rather than
    raising out of whichever assertion first touched a field it never sent.
    """
    reading = read_foreground(reply=process_info_reply(socket_path=socket_path, pane_id=pane_id))
    assert reading is not None, f"herdr returned no usable process reading for {pane_id!r}"
    return reading


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = _raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _forward(*, socket_path: str, raw: bytes) -> bytes:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(raw)
    try:
        return _read_frame(conn=sock) or b""
    finally:
        sock.close()


def _decline(*, request: dict[str, Any]) -> bytes:
    """The measured `changed: false` answer, echoing the panes the request named.

    Built from the request rather than from constants so the echo is correct by
    construction — an echo that happened to be wrong would land in the
    unresolved bucket instead, and this test would silently stop testing the
    decline.
    """
    params = request["params"]
    return (
        json.dumps(
            {
                "id": request["id"],
                "result": {
                    "type": "pane_swap",
                    "swap": {
                        "changed": False,
                        "reason": DECLINE_REASON,
                        "source_pane_id": params["source_pane_id"],
                        "target_pane_id": params["target_pane_id"],
                    },
                },
            }
        ).encode()
        + b"\n"
    )


def _serve_proxy(*, listener: socket.socket, real_socket: str, state: ProxyState) -> None:
    """Relay verbatim, except for a swap this proxy answers with a decline.

    An idle `accept` is NOT a shutdown. `socket.timeout` is an `OSError`
    subclass, so the predecessor's single `except OSError: return` ended this
    thread after the first quiet interval — and the readiness establishment the
    gate performs is exactly such an interval, because it talks to the real
    server directly and sends nothing through here. Only a genuine closure, which
    is this fixture's teardown closing the listener it opened, ends the loop.
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
            if request["method"] == "pane.swap" and state.decline:
                state.declined = True
                with contextlib.suppress(OSError):
                    conn.sendall(_decline(request=request))
                continue
            answered = _forward(socket_path=real_socket, raw=raw)
            if request["method"] == "pane.split" and answered:
                reply = json.loads(answered.split(b"\n")[0])
                state.created = str(reply["result"]["pane"]["pane_id"])
            try:
                conn.sendall(answered)
            except OSError:
                continue


def _start_server(*, session: str, scratch: Path, log_name: str) -> str:
    log = (scratch / log_name).open("wb")
    _ = subprocess.Popen(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, "--session", session, "server"],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(scratch),
    )
    address = _socket_for(session=session)
    deadline = time.monotonic() + SERVER_READY_TIMEOUT
    while time.monotonic() < deadline and not address.exists():
        time.sleep(0.1)
    log.close()
    assert address.exists(), (
        f"herdr session {session!r} never created {address}; "
        f"server log: {(scratch / log_name).read_text(errors='replace')[:500]}"
    )
    return str(address)


@dataclass(kw_only=True)
class OwnedProxies:
    """Every listener and relay thread this fixture opened, so it can close them.

    Teardown is EXACT rather than left to interpreter shutdown: closing a
    listener is what ends its relay thread now that an idle accept no longer
    does, and the join proves the thread this file started is the thread this
    file stopped.
    """

    listeners: list[socket.socket] = field(default_factory=list)
    threads: list[threading.Thread] = field(default_factory=list)

    def shut_down(self) -> None:
        for listener in self.listeners:
            with contextlib.suppress(OSError):
                listener.close()
        for thread in self.threads:
            thread.join(timeout=ACCEPT_POLL * 10)


def _build(
    *, session: str, scratch: Path, proxy_dir: Path, decline: bool, owned: OwnedProxies
) -> LiveProxiedTab:
    real_socket = _start_server(session=session, scratch=scratch, log_name=f"{session}.log")
    created = _raw_request(
        socket_path=real_socket,
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    original = str(created["result"]["root_pane"]["pane_id"])
    # An unrelated sibling in its OWN column, so any input or reshuffle reaching
    # it is unmistakable. The swap under test exchanges two panes in the
    # original's column; this one must come through untouched either way.
    sibling = _raw_request(
        socket_path=real_socket,
        method="pane.split",
        params={
            "target_pane_id": original,
            "direction": "right",
            "ratio": 0.5,
            "cwd": PANE_CWD,
            "focus": False,
        },
    )
    assert "result" in sibling, f"sibling split failed: {sibling}"
    state = ProxyState(decline=decline)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    proxy_socket = proxy_dir / f"{'decline' if decline else 'clean'}.sock"
    listener.bind(str(proxy_socket))
    listener.listen(16)
    relay = threading.Thread(
        target=_serve_proxy,
        kwargs={"listener": listener, "real_socket": real_socket, "state": state},
        daemon=True,
    )
    owned.listeners.append(listener)
    owned.threads.append(relay)
    relay.start()
    return LiveProxiedTab(
        real_socket=real_socket,
        proxy_socket=str(proxy_socket),
        original=original,
        unrelated=str(sibling["result"]["pane"]["pane_id"]),
        transient=startup_transient(scratch=scratch),
        state=state,
    )


@pytest.fixture(name="proxied")
def _proxied(*, tmp_path: Path) -> Iterator[Any]:
    """A factory: the declining harness and the clean one differ by one flag."""
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    proxy_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"hrdrn-{os.getpid()}"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    sessions: list[str] = []
    owned = OwnedProxies()

    def build(*, decline: bool) -> LiveProxiedTab:
        session = f"overseer-test-{os.getpid()}-{'decline' if decline else 'clean'}"
        sessions.append(session)
        return _build(
            session=session,
            scratch=tmp_path,
            proxy_dir=proxy_dir,
            decline=decline,
            owned=owned,
        )

    try:
        yield build
    finally:
        owned.shut_down()
        for session in sessions:
            _ = _cli(args=["--session", session, "server", "stop"])
            _ = _cli(args=["session", "delete", session])
        shutil.rmtree(proxy_dir, ignore_errors=True)


def _split_top(*, live: LiveProxiedTab) -> tuple[Any, ReadyShellGate]:
    """The real layout sequence, with the created pane's ready shell ESTABLISHED.

    The gate forwards every request to the shipped writer, so the socket, the
    deadline and the PEER VALIDATION stay exactly as the public facade runs them
    — against this proxy, whose pid and `/proc` start time the target names — and
    the shell proof is taken from that writer's own fields rather than rebuilt
    here. `split_window_top` is the three-line facade over this same call with
    this same proof.

    Its establishment requests go to the REAL socket, which is what keeps this
    fixture's setup input out of `ProxyState.writes()` and therefore out of the
    byte-level claim about what the WRITER delivered.

    The gate is returned alongside the outcome because an unestablished or
    expired readiness has to be gradeable as a FIXTURE failure by every caller,
    not swallowed here.
    """
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    gate = ReadyShellGate(
        inner=writer_module.HerdrWriter(timeout_seconds=10.0),
        socket_path=live.real_socket,
        startup_transient=live.transient,
        transient_name=TRANSIENT_NAME,
    )
    outcome = gate.place_above(
        target=identity.HerdrPaneTarget(
            socket_path=live.proxy_socket,
            server_pid=os.getpid(),
            server_starttime=starttime,
            pane_id=live.original,
        ),
        cwd=PANE_CWD,
        command=DAEMON_COMMAND,
        ratio=TOP_RATIO,
    )
    return outcome, gate


def _established(*, live: LiveProxiedTab, gate: ReadyShellGate) -> None:
    """Grade the fixture's own precondition before anything grades the adapter.

    Three facts, each named separately so a failure says which one was missing:
    the controlled child was observed in the EXACT pane the adapter created, that
    child exited on its own, and the pinned retained shell owns its foreground
    again. `refusal()` carries all three plus the expiry of any of their bounds.
    """
    assert gate.refusal() == "", gate.refusal()
    assert gate.gated == [live.state.created], (
        "the readiness gate must have established the pane the adapter actually "
        f"created; it gated {gate.gated} against created {live.state.created!r}"
    )
    transient = gate.transient
    assert transient is not None and transient.pid is not None, transient
    assert gate.retained is not None, "the retained shell was never pinned as an identity"
    assert parent_pid_of(pid=transient.pid) in (None, gate.retained.pid), (
        f"the controlled child {transient.pid} is not a child of the pinned retained "
        f"shell {gate.retained.pid}"
    )
    assert gate.departed == "", gate.departed
    established = gate.established
    assert established is not None and established.recovered is True, established


def _launched_child(*, live: LiveProxiedTab, pane_id: str) -> int:
    """The pid of the single `sleep` running under `pane_id`'s own retained shell.

    Waiting on the NAME rather than on the first foreground-group change is
    load-bearing, and this file used to open-code it wrongly. A shell runs a
    command by FORKING and then `exec`ing, so there is a real window in which the
    foreground group has already left the shell while the child is still `bash`.
    Measured on this host with an otherwise idle server, the first observed group
    change was `bash` rather than the command on 4 of 12 deliveries. The delivered
    helper keeps looking until the intended runtime is actually there — under the
    pane's own `shell_pid`, in the pane's own foreground group — and reports the
    expiry of its bound rather than returning the last thing it happened to see.
    """
    observed = await_occupying_child(
        read=lambda: process_info_reply(socket_path=live.real_socket, pane_id=pane_id),
        name=LAUNCH_NAME,
        poll=BoundedPoll(seconds=LAUNCH_TIMEOUT),
    )
    assert observed.pid is not None, observed.reason
    return observed.pid


def test_a_declined_swap_leaves_a_real_unmoved_pane_and_writes_nothing(*, proxied: Any):
    """The known partial layout, read from the real terminal rather than claimed.

    The split landed, so there is a pane; the swap did not, so it is still below
    the target; and because that whole state was observed, the outcome is
    CERTAIN while still naming the pane an operator has to deal with.

    The created pane's readiness is ESTABLISHED first, so a decline is graded
    against a pane that was provably launchable — otherwise the refusal this test
    attributes to the decline could equally be the occupied-pane refusal, which is
    a different guard reached one step earlier.
    """
    live = proxied(decline=True)

    outcome, gate = _split_top(live=live)

    _established(live=live, gate=gate)
    assert live.state.declined is True, "the decline was never actually injected"
    assert outcome.ok is False, "a declined swap is not a completed layout change"
    assert outcome.pane_id == live.state.created, "the created pane must still be named"
    assert outcome.effect_unknown is False, f"a legible decline is certain: {outcome.error}"
    assert DECLINE_REASON in outcome.error, outcome.error
    before = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert live.state.created in before, f"the real split must have landed: {before}"
    assert (
        before[live.state.created] > before[live.original]
    ), f"the pane must really be BELOW the target, which is what was declined: {before}"
    assert live.state.writes() == [], "the command was delivered after a declined swap"
    original_shell = _reading(socket_path=live.real_socket, pane_id=live.original).shell_pid
    for pane_id in (live.state.created, live.original, live.unrelated):
        reading = _reading(socket_path=live.real_socket, pane_id=pane_id)
        assert reading.is_idle(), f"{pane_id} was given something to run: {reading}"
        assert MARKER not in _capture(
            socket_path=live.real_socket, pane_id=pane_id
        ), f"the command text reached {pane_id}"
    assert gate.retained is not None and original_shell != gate.retained.pid, (
        "fixture precondition: the original pane's shell is not the created pane's, so the "
        "readings above are about three distinct shells"
    )


def test_the_same_harness_without_the_decline_still_launches(*, proxied: Any):
    """The control that makes the test above mean something.

    Identical proxy, identical real server, one flag different: here the swap is
    relayed and really lands, so the pane ends up above the target with the
    command running in its own retained shell.

    **Every one of those claims is about a pane whose readiness was ESTABLISHED
    first, which is the repair.** One real bounded child was observed owning that
    exact pane's foreground, observed exiting on its own, and the SAME pinned
    retained shell was observed owning its foreground again — and only then did
    the adapter take the reading it launches on. Unavailable or expired readiness
    fails this exercise as a FIXTURE failure naming what it saw, never as the
    adapter refusing a launch.
    """
    live = proxied(decline=False)

    outcome, gate = _split_top(live=live)

    _established(live=live, gate=gate)
    assert live.state.declined is False, "the control must inject nothing"
    assert outcome.ok is True, outcome.error
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert tops[outcome.pane_id] < tops[live.original], f"the swap must have landed: {tops}"
    child = _launched_child(live=live, pane_id=outcome.pane_id)
    reading = _reading(socket_path=live.real_socket, pane_id=outcome.pane_id)
    assert reading.pids_named(name=LAUNCH_NAME) == (child,), reading
    assert gate.retained is not None
    assert reading.shell_pid == gate.retained.pid, (
        f"the command must run under the SAME retained shell readiness was established "
        f"on ({gate.retained.pid}), not under {reading.shell_pid}"
    )
    assert (
        parent_pid_of(pid=child) == reading.shell_pid
    ), f"the launched process {child} is not a child of the retained shell {reading.shell_pid}"
    assert reading.is_idle() is False, "the command must run UNDER the shell, not replace it"
    assert live.state.writes() == [outcome.pane_id], live.state.writes()
