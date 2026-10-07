"""A REAL foreground child in the new pane withholds the launch, against live herdr.

The native counterpart of `tests/test_herdr_layout_launch_authorization.py`.
That file stages every unreadable, ambiguous and foreign process reading a
healthy server will not produce on demand; this one stages the single condition
that matters most and that only a real terminal can produce honestly — a
genuine process occupying the newly created pane's foreground at the moment the
daemon command would be written into it.

**The fault injection, stated plainly.** The writer is pointed at a forwarding
AF_UNIX proxy that this test process owns, with the real
`herdr --session <unique> server` behind it. The proxy forwards every request
and every reply BYTE-FOR-BYTE; it rewrites nothing. Its only effect is this:
when it sees the `pane.layout` request — which the adapter issues after the
REAL split and the REAL swap have already landed — it opens its own separate
connection to the real server and runs `sleep 300` in the created pane, then
OBSERVES that child before letting the layout request through. So by the time
the adapter takes its pre-launch reading, the pane is occupied by a real child
of a real shell, and the reading proving it comes from herdr rather than from
the surface under test.

**What "OBSERVES that child" has to mean, because this fixture used to get it
wrong and ACCUSE THE PRODUCT OF ITS OWN DEFECT.** The old wait returned as soon
as the pane's `foreground_process_group_id` differed from its `shell_pid` — any
difference, by any process. Measured on the operator host: shell `zsh` 3584980,
then foreground 3585294 named `mv`, a child of that shell's own startup. The
wait returned before `sleep` had ever run and stamped its precondition flag
anyway, so the pane the adapter read was genuinely IDLE and it returned
`outcome.ok=True` — correctly. `assert outcome.ok is False` therefore **FAILED**,
and the recurrence was recorded as a failing expected-refusal test.

**That direction is the whole point, and the opposite reading is the tempting
one.** This was a FAILING test against a CORRECT product, never a passing test
concealing a defect. Because no occupant was ever staged, the run carries NO
evidence either way about whether the adapter would accept a PROVEN occupied
pane — the question the exercise exists to ask was simply never put. A false
fixture premise produced a false accusation, and the repair's value is that the
same premise now fails as a FIXTURE failure that names what it saw.

Two sibling defects came out of the same loop: one real run raised
`KeyError: 'foreground_process_group_id'` inside the setup thread, and the loop
returned silently at its deadline, so a setup TIMEOUT and an established
precondition were the same return value.

**THE INTENDED INJECTION WAS NOT EVEN REACHABLE UNTIL THE CREATED PANE'S INITIAL
READINESS WAS ESTABLISHED, AND THAT IS WHAT THIS FILE WAS REPAIRED FOR
(work-item `overseer-hottfz`).** The adapter reads the created pane's process
info TWICE — once to ESTABLISH its retained shell right after the pane is proven,
and once to RECHECK that shell immediately before the write — and the `pane.layout`
request this fixture injects at falls BETWEEN them. So a created pane that is
already busy at the FIRST reading refuses one guard before the swap, the sequence
never asks for a layout, and the occupant this exercise exists to stage is never
injected at all. Measured on the operator host: `occupation` was None, the proxy
had seen `['pane.list', 'pane.split', 'pane.list', 'pane.process_info']` with
`created` at `w1:p3`, and the exercise failed on its own fixture premise.

That premise was then demonstrated deliberately in the factory sandbox BEFORE
this file was touched, rather than inferred from the guard ordering. With one
real `sleep 300` observed owning the created pane `w1:p3` (child 5383 under
retained shell 5376, foreground group 5383) at the request immediately before the
adapter's first reading, the shipped exercise relayed exactly
`['pane.list', 'pane.split', 'pane.list', 'pane.process_info']` — no `pane.swap`,
no `pane.layout`, `occupation` still None — the adapter refused with
`'w1:p3' is OCCUPIED: foreground group 5383 is not its retained shell 5376`, and
`_observed_occupant` failed by name with "the fixture's occupation step never
completed". Same pane id and same method list as the host receipt.

So the sequence now runs through `ReadyShellGate`, which precedes the FIRST
`pane.process_info` for the created pane — and only the first — with one real
bounded child staged in that exact pane, OBSERVED running under the pane's own
retained shell, observed EXITING on its own, and the SAME pinned retained shell
observed owning its foreground again. `_established` grades that precondition
before anything grades the adapter, so unavailable or expired initial readiness
is a FIXTURE failure naming what it saw.

**The gate is one-shot precisely so it does NOT swallow the occupancy this
exercise is about.** The occupant is injected later, at `pane.layout`, and the
reading that meets it is the adapter's SECOND one — which the gate forwards
untouched. `gate.gated` therefore holds exactly one pane while `gate.methods`
records two process-info requests, and every later assertion about the live
occupant and the writer's refusal is unchanged.

That staged initial child is the weaker claim deliberately: a bounded
DISCRIMINATING instance of a non-idle created pane, not a reproduction of the
operator's `zsh`/`mise`/`atuin` startup. The gate's establishment requests go to
the REAL socket, so this fixture's setup input never enters `adapter_writes()` or
`methods()` and the zero-delivery claim still describes the writer's stream alone.

**The proxy has to SURVIVE that establishment window, and it did not.** The
establishment talks to the real server directly, so the listener sits idle
throughout it — and `socket.timeout` is an `OSError` subclass, so the old
`except OSError: return` treated an ordinary idle accept as a shutdown and killed
the relay thread mid-sequence. A timeout is now distinguished from a real
closure, and teardown closes exactly the listener this fixture opened and joins
its thread.

So the occupation step now reports a `ChildObservation`: the pid of the single
foreground process named `sleep`, whose `/proc` parent is this pane's
`shell_pid` and whose process group IS the pane's foreground group — or the
reason none was observed. Every test below asserts that pid explicitly before
it asserts anything about the adapter, so a transient startup process, a
reading missing a field, a setup timeout and a dead setup thread all FAIL as
fixture failures rather than grading as an occupied-child proof. The helpers and
their deterministic controls live in `tests/test_herdr_live_observations.py`;
`test_a_real_transient_is_not_mistaken_for_the_requested_occupant` below is the
native control over real herdr. That control stages a bounded DISCRIMINATING
transient rather than claiming to reproduce the operator shell's startup: on a
shell that loads nothing the three exercises above passed before this change and
pass after it, as PRESERVATION controls over guards that already hold, and none
of this is a product Red.

The peer the writer validates is therefore the proxy — this test process — and
the target names its pid and `/proc` start time accordingly. That is a real peer
generation check against a real process, not a relaxation of it; the
generation-validation behaviour itself is proven against the live server in
`tests/test_herdr_live_observation.py`.

**Every control fact is read from the real server over a raw socket**, never from
the adapter's own account: the geometry that shows the created pane really did
end up above the original, the process reading that shows the occupying child is
still alive afterwards, and the three pane captures that show the command text
reached none of them.

Session isolation is herdr's own `--session` mechanism: the name carries this
test process's pid, and teardown stops and deletes BY THAT EXACT NAME, so no
other session — including the operator's `default` — is touched.
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
    TRANSIENT_SECONDS,
    BoundedPoll,
    ChildObservation,
    ForegroundReading,
    ReadyShellGate,
    ShellIdentityPin,
    await_idle_shell,
    await_occupying_child,
    occupying_child_pid,
    parent_pid_of,
    process_info_reply,
    read_foreground,
    starttime_of,
    startup_transient,
)

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
OCCUPY_TIMEOUT = 20.0
# Short enough that teardown closing the listener ends its relay thread promptly,
# long enough that the loop is not spinning. The establishment window this has to
# survive is seconds of real waiting with no connection arriving.
ACCEPT_POLL = 0.5
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
# Long-lived and inert, so the occupied reading is stable while the assertions
# run; teardown stops the whole session, so nothing is left behind.
OCCUPYING_COMMAND = "sleep 300"
OCCUPYING_NAME = "sleep"
# Deliberately not a runnable command: if it ever reaches a pane, it is visible
# in that pane's capture as itself.
DAEMON_COMMAND = "DO_NOT_SEND_TO_AN_OCCUPIED_PANE"


@dataclass(kw_only=True)
class ProxyState:
    """What the forwarding proxy saw, and what it injected.

    `occupation` is None until the injection step has RUN at all — which
    distinguishes a proxy whose thread died before reaching it from one that
    reached it and failed to observe the child, and neither from one that
    succeeded. The old `occupied: bool` collapsed all three into False.
    """

    created: str = ""
    occupation: ChildObservation | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)

    def adapter_writes(self) -> list[str]:
        """Every pane the ADAPTER sent input to — this fixture's own setup excluded.

        The injected `sleep` goes to the real server on a separate connection
        that never passes through the listener, and the readiness gate's
        controlled child goes the same way, so anything recorded here was
        written by the surface under test. That separation is the whole reason
        both of them are pointed at the real socket rather than at the proxy.
        """
        return [
            str(request["params"].get("pane_id"))
            for request in self.requests
            if request["method"] == "pane.send_input"
        ]

    def methods(self) -> list[str]:
        return [str(request["method"]) for request in self.requests]


@dataclass(frozen=True, kw_only=True)
class LiveProxiedTab:
    """A real herdr tab, plus the forwarding proxy the writer is pointed at."""

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


def _reading(*, socket_path: str, pane_id: str) -> ForegroundReading:
    """`pane_id`'s live process reading, or an explicit FIXTURE failure.

    An unusable reply is a failed control read rather than a fact about the
    pane, so it stops the exercise here instead of raising a `KeyError` out of
    whichever assertion happened to touch the missing field first.
    """
    reading = read_foreground(reply=process_info_reply(socket_path=socket_path, pane_id=pane_id))
    assert reading is not None, f"herdr returned no usable process reading for {pane_id!r}"
    return reading


def _await_named(*, socket_path: str, pane_id: str, name: str) -> ForegroundReading:
    """The first reading in which `pane_id` lists a foreground process `name`.

    The READING is returned, not just a pid, so a control can interrogate one
    single point-in-time observation from several angles without a second round
    trip the subject could change under.
    """
    deadline = time.monotonic() + OCCUPY_TIMEOUT
    while time.monotonic() < deadline:
        reading = _reading(socket_path=socket_path, pane_id=pane_id)
        if reading.pids_named(name=name):
            return reading
        time.sleep(0.1)
    pytest.fail(f"{pane_id!r} never reported a foreground process named {name!r}")


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = _raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={
            "pane_id": pane_id,
            "source": "visible",
            "format": "text",
            "strip_ansi": True,
        },
    )
    return str(reply["result"]["read"]["text"])


def _geometry(*, socket_path: str, pane_id: str) -> dict[str, int]:
    """Every pane's TOP row on the tab, read from the real server."""
    reply = _raw_request(socket_path=socket_path, method="pane.layout", params={"pane_id": pane_id})
    return {
        str(pane["pane_id"]): int(pane["rect"]["y"]) for pane in reply["result"]["layout"]["panes"]
    }


def _run_in_pane(*, socket_path: str, pane_id: str, command: str) -> None:
    _ = _raw_request(
        socket_path=socket_path,
        method="pane.send_input",
        params={"pane_id": pane_id, "text": command, "keys": ["Enter"]},
    )


def _occupy(*, socket_path: str, pane_id: str) -> ChildObservation:
    """Start a REAL foreground child in `pane_id`, and OBSERVE that exact child.

    Returns the observation rather than stamping a flag, so the caller cannot
    read a transient startup process, an unusable reading or an expired
    deadline as an established occupation. See this module's docstring for the
    three measured ways the predecessor did exactly that.
    """
    _run_in_pane(socket_path=socket_path, pane_id=pane_id, command=OCCUPYING_COMMAND)
    return await_occupying_child(
        read=lambda: process_info_reply(socket_path=socket_path, pane_id=pane_id),
        name=OCCUPYING_NAME,
        poll=BoundedPoll(seconds=OCCUPY_TIMEOUT),
    )


def _forward(*, socket_path: str, raw: bytes) -> bytes:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(raw)
    try:
        return _read_frame(conn=sock) or b""
    finally:
        sock.close()


def _inject_occupant(*, real_socket: str, state: ProxyState) -> ChildObservation:
    """The occupation step, with its own socket failure reported rather than raised.

    A raise here would die inside the daemon proxy thread with nothing watching,
    leaving `occupation` at None — which is why None is "the step never
    completed" and the tests refuse it.
    """
    try:
        return _occupy(socket_path=real_socket, pane_id=state.created)
    except OSError as failed:
        return ChildObservation(pid=None, reason=f"the occupation step failed: {failed}")


def _serve_proxy(*, listener: socket.socket, real_socket: str, state: ProxyState) -> None:
    """Forward requests verbatim, occupying the created pane before the layout read.

    An idle `accept` is NOT a shutdown. `socket.timeout` is an `OSError`
    subclass, so the predecessor's single `except OSError: return` ended this
    thread after the first quiet interval — and the initial-readiness
    establishment the gate performs is exactly such an interval, because it talks
    to the real server directly and sends nothing through here. Only a genuine
    closure, which is this fixture's teardown closing the listener it opened,
    ends the loop.
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
            if request["method"] == "pane.layout" and state.created and state.occupation is None:
                state.occupation = _inject_occupant(real_socket=real_socket, state=state)
            answered = _forward(socket_path=real_socket, raw=raw)
            if request["method"] == "pane.split" and answered:
                reply = json.loads(answered.split(b"\n")[0])
                state.created = str(reply["result"]["pane"]["pane_id"])
            try:
                conn.sendall(answered)
            except OSError:
                continue


def _start_server(*, session: str, scratch: Path) -> str:
    log = (scratch / "server.log").open("wb")
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
        f"server log: {(scratch / 'server.log').read_text(errors='replace')[:500]}"
    )
    return str(address)


@dataclass(kw_only=True)
class OwnedProxy:
    """The listener and relay thread this fixture opened, so it can close them.

    Teardown is EXACT rather than left to interpreter shutdown: closing the
    listener is what ends the relay thread now that an idle accept no longer
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


def _build_tab(
    *, session: str, scratch: Path, proxy_dir: Path, owned: OwnedProxy
) -> LiveProxiedTab:
    real_socket = _start_server(session=session, scratch=scratch)
    created = _raw_request(
        socket_path=real_socket,
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    original = str(created["result"]["root_pane"]["pane_id"])
    # An unrelated sibling in its OWN column, so any input or reshuffle landing
    # there is unmistakable.
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
    state = ProxyState()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    proxy_socket = proxy_dir / "p.sock"
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


@pytest.fixture(name="live")
def _live(*, tmp_path: Path) -> Iterator[LiveProxiedTab]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-occupied"
    proxy_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"hrdrp-{os.getpid()}"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    owned = OwnedProxy()
    built = _build_tab(session=session, scratch=tmp_path, proxy_dir=proxy_dir, owned=owned)
    try:
        yield built
    finally:
        owned.shut_down()
        _ = _cli(args=["--session", session, "server", "stop"])
        _ = _cli(args=["session", "delete", session])
        shutil.rmtree(proxy_dir, ignore_errors=True)


def _split_top(*, live: LiveProxiedTab) -> tuple[Any, ReadyShellGate]:
    """The real layout sequence, with the created pane's INITIAL readiness established.

    The gate forwards every request to the shipped writer, so the socket, the
    deadline and the PEER VALIDATION stay exactly as the public facade runs them
    — against this proxy, whose pid and `/proc` start time the target names — and
    the shell proof is taken from that writer's own fields rather than rebuilt
    here. `split_window_top` is the three-line facade over this same call with
    this same proof.

    It establishes the FIRST `pane.process_info` for the created pane and nothing
    else, which is what keeps this exercise's subject intact: the occupant is
    injected afterwards, at `pane.layout`, and the reading that meets it is the
    adapter's SECOND one, relayed untouched.

    Its establishment requests go to the REAL socket, which keeps this fixture's
    setup input out of `ProxyState.adapter_writes()` and therefore out of the
    byte-level claim that nothing was delivered, and out of `methods()` so the
    `pane.swap` count below still describes the WRITER's request stream alone.

    The gate is returned alongside the outcome because unavailable or expired
    initial readiness has to be gradeable as a FIXTURE failure, not swallowed
    here.
    """
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    gate = ReadyShellGate(
        inner=writer_module.HerdrWriter(timeout_seconds=30.0),
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
    """Grade the INITIAL readiness premise before anything grades the adapter.

    Four facts, each named separately so a failure says which one was missing:
    the controlled child was observed in the EXACT pane the adapter created,
    under that pane's own pinned retained shell, it exited on its own, and that
    same shell identity owns its foreground again. `refusal()` carries all of
    them plus the expiry of any of their bounds, so an unavailable or expired
    establishment fails HERE, by name, rather than being reported as the adapter
    declining to launch.

    `gated` is asserted to hold exactly ONE pane, which is the other half of the
    claim: the establishment ran once, before the first reading, and the adapter's
    second reading — the one that meets the injected occupant — was relayed
    untouched.
    """
    assert gate.refusal() == "", gate.refusal()
    assert gate.gated == [live.state.created], (
        "the readiness gate must have established the pane the adapter actually "
        f"created, exactly once; it gated {gate.gated} against created {live.state.created!r}"
    )
    transient = gate.transient
    assert transient is not None and transient.pid is not None, transient
    assert gate.retained is not None, "the retained shell was never pinned as an identity"
    assert parent_pid_of(pid=transient.pid) in (None, gate.retained.pid), (
        f"the controlled child {transient.pid} is not a child of the pinned retained "
        f"shell {gate.retained.pid}"
    )
    assert gate.departed == "", gate.departed
    recovery = gate.established
    assert recovery is not None and recovery.recovered is True, recovery
    assert gate.methods.count("pane.process_info") == 2, (
        "the adapter must still take BOTH of its readings — the established one and the "
        f"recheck that meets the occupant: {gate.methods}"
    )


def _observed_occupant(*, live: LiveProxiedTab) -> int:
    """The pid of the child the fixture actually OBSERVED occupying the new pane.

    Every test below goes through this, so a fixture that failed to occupy the
    pane fails as a FIXTURE — naming what it saw instead — rather than being
    reported as a proof about the adapter's authorization.
    """
    occupation = live.state.occupation
    assert occupation is not None, (
        "the fixture's occupation step never completed; the proxy saw "
        f"{live.state.methods()} and created {live.state.created!r}"
    )
    assert occupation.pid is not None, f"the new pane was never occupied: {occupation.reason}"
    return occupation.pid


def test_a_really_occupied_new_pane_receives_no_command_or_enter_bytes(*, live: LiveProxiedTab):
    """THE native proof: a real child owns the new pane, so nothing is written to it.

    The adapter must issue no `pane.send_input` at all — that is the byte-level
    statement — and the created pane's own capture must not contain the command
    text, which is the statement read from the terminal itself.

    The pane's INITIAL readiness is established first, so the refusal asserted
    here is the occupied-pane guard meeting the occupant this fixture staged at
    `pane.layout` — not the same guard meeting a pane that was busy before the
    swap was ever asked for, which is the measured shape that stopped the
    sequence one step early and never injected anything.
    """
    outcome, gate = _split_top(live=live)

    _established(live=live, gate=gate)
    child = _observed_occupant(live=live)
    assert live.state.methods().count("pane.layout") == 1, (
        "the one-time readiness gate must not have swallowed the later injection: the "
        f"writer never reached its layout read: {live.state.methods()}"
    )
    assert gate.transient is not None and child != gate.transient.pid, (
        f"the occupant {child} is the readiness gate's own bounded child {gate.transient}, not "
        "the distinct occupant this exercise injected after the layout"
    )
    assert starttime_of(pid=child) is not None, (
        f"the observed occupant {child} was gone before the adapter's reading, so the "
        "pane it read was not the occupied pane this exercise staged"
    )
    assert outcome.ok is False, "a pane whose foreground is a live child is not launchable"
    assert outcome.pane_id == live.state.created, "the created pane must still be named"
    assert outcome.effect_unknown is False, outcome.error
    assert live.state.adapter_writes() == [], "the adapter wrote into a pane it could not prove"
    assert DAEMON_COMMAND not in _capture(
        socket_path=live.real_socket, pane_id=live.state.created
    ), "the command text reached the occupied pane"


def test_the_refusal_preserves_the_partial_layout_and_the_occupying_child(*, live: LiveProxiedTab):
    """Refusing the launch must not undo the split, the swap, or kill the occupant.

    The pane is real and correctly placed; the honest outcome is to leave it
    exactly where it is and say so, because that is the state an operator has to
    re-observe. Repeating the swap would push it back below the target.

    The swap is only reached at all because the pane's INITIAL readiness was
    established, so "the proven swap must not be undone" is a claim about a swap
    that really happened rather than about one the sequence stopped short of.
    """
    outcome, gate = _split_top(live=live)

    _established(live=live, gate=gate)
    child = _observed_occupant(live=live)
    assert outcome.ok is False, "precondition: the launch was refused"
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert live.state.created in tops, "the created pane must survive the refusal"
    assert (
        tops[live.state.created] < tops[live.original]
    ), "the proven swap must not be undone or repeated"
    reading = _reading(socket_path=live.real_socket, pane_id=live.state.created)
    assert reading.is_idle() is False, "the occupying child must not be terminated"
    # The SAME pid that was observed, not merely some process wearing the same
    # name: a replacement child would satisfy a name-only assertion.
    assert child in reading.pids_named(name=OCCUPYING_NAME), reading
    assert starttime_of(pid=child) is not None, f"the occupant {child} was killed"
    assert live.state.methods().count("pane.swap") == 1, live.state.methods()


def test_the_original_pane_and_its_unrelated_sibling_receive_nothing(*, live: LiveProxiedTab):
    """The supervised agent and the bystander must both come through untouched.

    The readiness establishment is confined to the pane the ADAPTER created, so
    these two panes are the same bystanders they always were — which the idle
    readings and the unchanged original shell below are what prove.
    """
    before = _geometry(socket_path=live.real_socket, pane_id=live.original)
    original_shell = _reading(socket_path=live.real_socket, pane_id=live.original).shell_pid

    outcome, gate = _split_top(live=live)

    _established(live=live, gate=gate)
    _ = _observed_occupant(live=live)
    assert outcome.ok is False, "precondition: the launch was refused"
    for pane_id in (live.original, live.unrelated):
        reading = _reading(socket_path=live.real_socket, pane_id=pane_id)
        assert reading.is_idle(), f"{pane_id} was given something to run: {reading}"
        assert DAEMON_COMMAND not in _capture(
            socket_path=live.real_socket, pane_id=pane_id
        ), f"the command text reached {pane_id}"
    after = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert after[live.unrelated] == before[live.unrelated], "the sibling moved"
    assert (
        _reading(socket_path=live.real_socket, pane_id=live.original).shell_pid == original_shell
    ), "the original pane's shell was replaced"


def test_a_real_transient_is_not_mistaken_for_the_requested_occupant(
    *, live: LiveProxiedTab, tmp_path: Path
):
    """The NATIVE control for the measured fixture defect, over real herdr.

    A real, distinctly named, self-terminating child is run in a real pane and
    OBSERVED owning its foreground — the condition the old wait accepted as
    proof of occupation. From that one reading, asking for the REQUESTED name
    must refuse; the requested `sleep` is then started for real and the same
    helper must establish it. Both halves come from the same instrument, so the
    control cannot pass by refusing everything.

    Driven on a pane this control creates itself rather than on the one the
    adapter makes: the subject here is the OBSERVATION, and entangling it with
    a layout sequence would make a refusal ambiguous between the two.
    """
    transient = startup_transient(scratch=tmp_path)
    pane = _raw_request(
        socket_path=live.real_socket,
        method="pane.split",
        params={
            "target_pane_id": live.unrelated,
            "direction": "down",
            "ratio": 0.5,
            "cwd": PANE_CWD,
            "focus": False,
        },
    )
    assert "result" in pane, f"control split failed: {pane}"
    pane_id = str(pane["result"]["pane"]["pane_id"])

    _run_in_pane(socket_path=live.real_socket, pane_id=pane_id, command=transient)
    running = _await_named(socket_path=live.real_socket, pane_id=pane_id, name=TRANSIENT_NAME)
    assert running.is_idle() is False, "the transient really left the shell's foreground group"
    refused = occupying_child_pid(reading=running, name=OCCUPYING_NAME)
    assert refused.pid is None, "a real startup transient was accepted as the requested child"
    assert OCCUPYING_NAME in refused.reason, refused.reason

    _run_in_pane(socket_path=live.real_socket, pane_id=pane_id, command=OCCUPYING_COMMAND)
    observed = await_occupying_child(
        read=lambda: process_info_reply(socket_path=live.real_socket, pane_id=pane_id),
        name=OCCUPYING_NAME,
        poll=BoundedPoll(seconds=OCCUPY_TIMEOUT + TRANSIENT_SECONDS),
    )
    assert observed.pid is not None, observed.reason
    assert parent_pid_of(pid=observed.pid) == running.shell_pid, (
        f"the observed {OCCUPYING_NAME} {observed.pid} is not a child of the pane's "
        f"retained shell {running.shell_pid}"
    )


def test_the_staged_transient_is_a_bounded_child_the_shell_recovers_from(
    *, live: LiveProxiedTab, tmp_path: Path
):
    """The transient's WHOLE lifecycle, over real herdr: run, bounded, gone, recovered.

    The control above proves the staged transient is not mistaken for the
    requested child. This one proves it is a real child at all — the property the
    measured uutils-host failure destroyed, where the command exited 1 in 0.2
    seconds and no `ovstartup` ever existed, so every exercise that staged one
    refused its own fixture premise.

    Four real observations on one pane this control creates itself, each from the
    server or from `/proc` rather than from the surface under test:

      1. the pane's retained shell as an IDENTITY — pid AND start time — before
         anything runs in it;
      2. the transient observed by its REQUESTED name, as that shell's own
         `/proc` child, owning the pane's foreground group;
      3. its NATURAL exit: this control sends no signal, and the pid no longer
         carries the start time it was observed with, so the process that left
         is the one that arrived rather than a recycled number;
      4. SEPARATELY, within its own bound, the SAME shell identity owning its
         foreground again, with the pane still open.

    Step 4 is `await_idle_shell` doing the job a predecessor inferred from step 3
    — the child exiting is not the shell recovering — and step 1's pin is what
    makes "the same shell" a claim about a process rather than about an integer.
    """
    pane = _raw_request(
        socket_path=live.real_socket,
        method="pane.split",
        params={
            "target_pane_id": live.unrelated,
            "direction": "down",
            "ratio": 0.5,
            "cwd": PANE_CWD,
            "focus": False,
        },
    )
    assert "result" in pane, f"control split failed: {pane}"
    pane_id = str(pane["result"]["pane"]["pane_id"])

    def read() -> dict[str, Any]:
        return process_info_reply(socket_path=live.real_socket, pane_id=pane_id)

    shell = _reading(socket_path=live.real_socket, pane_id=pane_id).shell_pid
    shell_starttime = starttime_of(pid=shell)
    assert shell_starttime is not None, f"the pane's shell {shell} must be alive to begin with"

    _run_in_pane(
        socket_path=live.real_socket, pane_id=pane_id, command=startup_transient(scratch=tmp_path)
    )
    observed = await_occupying_child(
        read=read, name=TRANSIENT_NAME, poll=BoundedPoll(seconds=OCCUPY_TIMEOUT)
    )
    assert observed.pid is not None, observed.reason
    child_starttime = starttime_of(pid=observed.pid)
    assert child_starttime is not None, f"{TRANSIENT_NAME} {observed.pid} was gone when observed"

    recovery = await_idle_shell(
        read=read,
        pane_id=pane_id,
        poll=BoundedPoll(seconds=OCCUPY_TIMEOUT + TRANSIENT_SECONDS),
        expected=ShellIdentityPin(pid=shell, starttime=shell_starttime),
    )

    assert recovery.recovered is True, recovery.reason
    assert starttime_of(pid=observed.pid) != child_starttime, (
        f"{TRANSIENT_NAME} {observed.pid} still carries start time {child_starttime}, so the "
        "pane reported an idle shell while its declared transient was still running"
    )
