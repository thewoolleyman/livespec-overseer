"""A REAL swap that landed, with its answer broken — the effect is UNRESOLVED.

The native counterpart of `tests/test_herdr_layout_unresolved_swap_effect.py`.
That file stages the malformed shapes a healthy server will not emit; this one
stages the condition that gives them their meaning and that only a real
terminal can supply: the swap ACTUALLY HAPPENED, and the adapter cannot tell.

**The fault injection, stated plainly — and it is the whole method here.** The
writer is pointed at a forwarding AF_UNIX proxy owned by this test process, with
a real `herdr --session <unique> server` behind it. Every request and reply is
relayed byte-for-byte except for exactly one deliberate fault per test:

  - `corrupt the swap answer` — the `pane.swap` request IS forwarded, so the
    real server really exchanges the two panes, and only then is its reply
    rewritten so that `result.swap` is a bare string. The mutation happened; its
    account of itself is unusable.
  - `withhold the geometry answer` — everything up to and including the real
    swap is relayed untouched, and the following `pane.layout` request is then
    dropped: the proxy closes the connection without answering, which is the
    client-side shape of a committed request that goes unanswered. Nothing is
    mutated by withholding a READ; what is lost is the evidence.

In both cases the test then reads the REAL geometry from the REAL server over a
raw socket and shows the swap did land — the created pane really is above the
target. That reading is the point of doing this natively: it proves the
`effect_unknown=True` the adapter reports is honest uncertainty about a mutation
that genuinely occurred, rather than a label on a call that never did anything.

A repeat is what the flag exists to prevent, and it is asserted directly: the
proxy counts requests, so "the swap was not resent" and "no command was
launched" are measurements rather than inferences. Repeating a landed swap would
put the daemon pane back BELOW the session it supervises.

**NEITHER FAULT WAS REACHABLE WITHOUT ESTABLISHING THE CREATED PANE'S READINESS
FIRST, and that is what this file was repaired for (work-item `overseer-dihsef`).**
The pane is created BY the adapter and read three round trips later, so no setup
beforehand can influence what is in its foreground at that instant; the adapter's
pre-launch reading is taken BEFORE the swap, so an occupied created pane stops
the sequence one guard EARLIER than either fault here, and the exercise then
reports a refusal that has nothing to do with the swap it meant to test. That was
demonstrated separately rather than inferred from the shared guard ordering:
driving THIS module's own public writer against a real `sleep 300` observed owning
the created pane `w1:p2` (child 5844 under retained shell 5835), the relayed
request list stopped at `['pane.list', 'pane.split', 'pane.list',
'pane.process_info']` — no `pane.swap` ever sent, the withheld-geometry fault
never injected — and the outcome was `'w1:p2' is OCCUPIED: foreground group 5844
is not its retained shell 5835`.

So `_split_top` runs the real sequence through `ReadyShellGate`, which stages one
real bounded child in that exact pane, OBSERVES it, waits for it to exit and for
the SAME pinned retained shell to own its foreground again, and only then lets the
adapter read. `_assert_unresolved_but_landed` grades that precondition before it
grades anything about the adapter, so unavailable or expired readiness is a
FIXTURE failure naming what it saw.

What that staged child does and does not stand for is the weaker claim
deliberately: it is a bounded DISCRIMINATING instance of a non-idle created pane,
not a reproduction of the operator host's `zsh`/`mise`/`atuin` startup, and the
withheld-geometry node's ORIGINAL host failure remains unresolved — it passed when
re-run alone on the host, and nothing here reproduces whatever made it fail inside
the aggregate. `tests/test_herdr_live_observations.py` carries that framing in
full.

**The proxy has to SURVIVE that establishment window, and it did not.** The
establishment talks to the real server directly, so the listener sits idle
throughout it — and `socket.timeout` is an `OSError` subclass, so the old
`except OSError: return` treated an ordinary idle accept as a shutdown and killed
the relay thread mid-sequence. A timeout is now distinguished from a real closure,
and teardown closes exactly the listeners this fixture opened and joins their
threads.

The peer the writer validates is the proxy — this test process — and the target
names its pid and `/proc` start time accordingly; that is a real generation
check against a real process, proven against the live server itself in
`tests/test_herdr_live_observation.py`.

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
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from test_herdr_live_observations import (
    OwnedServer,
    PaneReadiness,
    ReadyWriter,
    parent_pid_of,
    registered_login_shells,
    start_owned_server,
    startup_transient,
    stop_owned_server,
)

__all__: list[str] = []

# Short enough that teardown closing a listener ends its relay thread promptly,
# long enough that the loop is not spinning. The establishment window this has to
# survive is seconds of real waiting with no connection arriving.
ACCEPT_POLL = 0.5
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
DAEMON_COMMAND = "DO_NOT_SEND_PAST_AN_UNRESOLVED_SWAP"

CORRUPT_SWAP = "corrupt-swap-answer"
WITHHOLD_LAYOUT = "withhold-geometry-answer"


@dataclass(kw_only=True)
class ProxyState:
    """What the forwarding proxy relayed, and which single fault it injected."""

    fault: str
    created: str = ""
    injected: bool = False
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
    """A real herdr tab plus the faulting proxy the writer is pointed at."""

    real_socket: str
    proxy_socket: str
    original: str
    transient: str
    state: ProxyState


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
    """Every pane's TOP row on the tab, read from the real server."""
    reply = _raw_request(socket_path=socket_path, method="pane.layout", params={"pane_id": pane_id})
    return {
        str(pane["pane_id"]): int(pane["rect"]["y"]) for pane in reply["result"]["layout"]["panes"]
    }


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


def _corrupted(*, answered: bytes) -> bytes:
    """The real reply with its `swap` member replaced by an unusable string.

    The id is left alone deliberately: the transport's own id matching must keep
    accepting this as the answer to THIS request, so the only thing wrong with
    it is that it cannot be read.
    """
    reply = json.loads(answered.split(b"\n")[0])
    reply["result"]["swap"] = "corrupted by deliberate fault injection"
    return json.dumps(reply).encode() + b"\n"


def _serve_proxy(*, listener: socket.socket, real_socket: str, state: ProxyState) -> None:
    """Relay verbatim, injecting exactly one fault once the real swap has landed.

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
            if request["method"] == "pane.layout" and state.fault == WITHHOLD_LAYOUT:
                # Drop the READ, answering nothing. The swap already landed.
                state.injected = True
                continue
            answered = _forward(socket_path=real_socket, raw=raw)
            if request["method"] == "pane.split" and answered:
                reply = json.loads(answered.split(b"\n")[0])
                state.created = str(reply["result"]["pane"]["pane_id"])
            if request["method"] == "pane.swap" and state.fault == CORRUPT_SWAP and answered:
                answered = _corrupted(answered=answered)
                state.injected = True
            try:
                conn.sendall(answered)
            except OSError:
                continue


def _start_server(*, session: str, scratch: Path) -> OwnedServer:
    """One OWNED server whose panes run a DECLARED minimal shell, plus its root pane.

    The shared seam is what makes that shell the fixture's choice rather than an
    inherited one, and it encloses its own socket wait and workspace creation in
    cleanup; see `tests/test_herdr_live_observations.py`.
    """
    return start_owned_server(session=session, scratch=scratch, cwd=PANE_CWD)


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
    *, session: str, scratch: Path, proxy_dir: Path, fault: str, owned: OwnedProxies
) -> LiveProxiedTab:
    owned_server = _start_server(session=session, scratch=scratch)
    real_socket = owned_server.socket_path
    original = owned_server.root
    state = ProxyState(fault=fault)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    proxy_socket = proxy_dir / f"{fault}.sock"
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
        transient=startup_transient(scratch=scratch),
        state=state,
    )


@pytest.fixture(name="faulted")
def _faulted(*, tmp_path: Path) -> Iterator[Any]:
    """A factory, because each test injects a DIFFERENT single fault."""
    proxy_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"hrdru-{os.getpid()}"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    sessions: list[str] = []
    owned = OwnedProxies()

    def build(*, fault: str) -> LiveProxiedTab:
        session = f"overseer-test-{os.getpid()}-{fault}"
        sessions.append(session)
        return _build(
            session=session, scratch=tmp_path, proxy_dir=proxy_dir, fault=fault, owned=owned
        )

    try:
        yield build
    finally:
        owned.shut_down()
        for session in sessions:
            stop_owned_server(session=session)
        shutil.rmtree(proxy_dir, ignore_errors=True)


def _split_top(*, live: LiveProxiedTab) -> tuple[Any, PaneReadiness]:
    """The real layout sequence, with the created pane's ready shell ESTABLISHED.

    The gate forwards every request to the shipped writer, so the socket, the
    deadline and the PEER VALIDATION stay exactly as the public facade runs them
    — against this proxy, whose pid and `/proc` start time the target names — and
    the shell proof is taken from that writer's own fields rather than rebuilt
    here. `split_window_top` is the three-line facade over this same call with
    this same proof.

    Its establishment requests go to the REAL socket, which keeps this fixture's
    setup input out of `ProxyState.writes()` and therefore out of the byte-level
    claim that nothing was launched past the fault. It also keeps them out of
    `methods()`, so the `pane.swap` and `pane.layout` counts below still describe
    the WRITER's request stream alone.

    The gate is returned alongside the outcome because an unestablished or expired
    readiness has to be gradeable as a FIXTURE failure, not swallowed here.
    """
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    assert (
        ReadyWriter.split_window_top is writer_module.HerdrWriter.split_window_top
    ), "the exercise must enter the SHIPPED public facade, not a fixture reimplementation"
    readiness = PaneReadiness(
        socket_path=live.real_socket,
        transient=live.transient,
        registered=registered_login_shells(),
    )
    outcome = ReadyWriter(readiness=readiness, timeout_seconds=10.0).split_window_top(
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
    return outcome, readiness


def _assert_readiness_was_established(*, live: LiveProxiedTab, readiness: PaneReadiness) -> None:
    """Grade the fixture's own precondition before anything grades the adapter.

    Each fact named separately so a failure says which one was missing: the step ran
    exactly once and for the EXACT pane the adapter created, the controlled child was
    that pane's own pinned retained shell's child, it exited on its own, that shell
    owns its foreground again, and the pane's server-reported name and kernel
    executable describe one program. `refusal()` carries all of those plus the expiry
    of any of their bounds.

    Without this, an occupied or incoherent created pane refuses one guard BEFORE the
    swap, so neither fault below is ever reached and the exercise reports a refusal
    about something else entirely — the measured shape recorded in this module's
    docstring.
    """
    assert readiness.panes == [live.state.created], (
        "readiness must have been established exactly once, for the pane the adapter "
        f"created; it ran for {readiness.panes} against created {live.state.created!r}"
    )
    assert readiness.refusal() == "", readiness.refusal()
    gate = readiness.gate
    assert gate is not None, "a refusal-free run established something, so it must hold a gate"
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
    identity = readiness.identity
    assert identity is not None and identity.coherent is True, readiness.refusal()
    assert identity.shell_pid == gate.retained.pid, (
        f"the coherent identity describes shell {identity.shell_pid} while the pinned retained "
        f"shell is {gate.retained.pid}"
    )


def _assert_unresolved_but_landed(*, live: LiveProxiedTab, outcome: Any) -> None:
    """The shared verdict: a real swap landed, and the adapter honestly cannot tell."""
    assert live.state.injected is True, "the fault was never actually injected"
    assert outcome.ok is False, "an unusable answer is not a completed layout change"
    assert (
        outcome.pane_id == live.state.created
    ), "the created pane must be named for re-observation"
    assert outcome.effect_unknown is True, f"reported certain: {outcome.error}"
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert live.state.created in tops, tops
    assert tops[live.state.created] < tops[live.original], (
        "fixture precondition: the REAL swap must have landed, which is what makes "
        f"the uncertainty real rather than nominal; geometry is {tops}"
    )
    assert live.state.methods().count("pane.swap") == 1, live.state.methods()
    assert live.state.writes() == [], "the command was launched past an unresolved swap"
    assert DAEMON_COMMAND not in _capture(
        socket_path=live.real_socket, pane_id=live.state.created
    ), "the command text reached the created pane"
    assert DAEMON_COMMAND not in _capture(
        socket_path=live.real_socket, pane_id=live.original
    ), "the command text reached the supervised pane"


def test_a_landed_swap_with_a_corrupted_answer_is_unresolved(*, faulted: Any):
    """The real panes were exchanged; the reply describing it cannot be read.

    The created pane's readiness is ESTABLISHED before the swap is asked for, so
    the swap is actually reached and the corruption is actually injected — which
    is what makes the uncertainty asserted below about a mutation that occurred.
    """
    live = faulted(fault=CORRUPT_SWAP)

    outcome, readiness = _split_top(live=live)

    _assert_readiness_was_established(live=live, readiness=readiness)
    _assert_unresolved_but_landed(live=live, outcome=outcome)
    assert (
        "pane.layout" not in live.state.methods()
    ), "an unreadable swap answer must stop the sequence before the placement read"


def test_a_landed_swap_with_a_withheld_geometry_answer_is_unresolved(*, faulted: Any):
    """The swap answered properly; the placement evidence never came back.

    The adapter believed a well-formed acknowledgement and then could not
    confirm it against the rectangles, which is exactly the state in which
    re-running anything is forbidden and re-observing is the only move.
    """
    live = faulted(fault=WITHHOLD_LAYOUT)

    outcome, readiness = _split_top(live=live)

    _assert_readiness_was_established(live=live, readiness=readiness)
    _assert_unresolved_but_landed(live=live, outcome=outcome)
    assert (
        live.state.methods().count("pane.layout") == 1
    ), "the withheld placement read must not be retried"
