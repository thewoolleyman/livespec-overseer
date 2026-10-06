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

The peer the writer validates is the proxy — this test process — and the target
names its pid and `/proc` start time accordingly; that is a real generation
check against a real process, proven against the live server itself in
`tests/test_herdr_live_observation.py`.

Session isolation is herdr's own `--session` mechanism: the name carries this
test process's pid, and teardown stops and deletes BY THAT EXACT NAME.
"""

from __future__ import annotations

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

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
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
    """Relay verbatim, injecting exactly one fault once the real swap has landed."""
    listener.settimeout(5.0)
    while True:
        try:
            conn, _peer = listener.accept()
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


def _build(*, session: str, scratch: Path, proxy_dir: Path, fault: str) -> LiveProxiedTab:
    real_socket = _start_server(session=session, scratch=scratch)
    created = _raw_request(
        socket_path=real_socket,
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    original = str(created["result"]["root_pane"]["pane_id"])
    state = ProxyState(fault=fault)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    proxy_socket = proxy_dir / f"{fault}.sock"
    listener.bind(str(proxy_socket))
    listener.listen(16)
    threading.Thread(
        target=_serve_proxy,
        kwargs={"listener": listener, "real_socket": real_socket, "state": state},
        daemon=True,
    ).start()
    return LiveProxiedTab(
        real_socket=real_socket,
        proxy_socket=str(proxy_socket),
        original=original,
        state=state,
    )


@pytest.fixture(name="faulted")
def _faulted(*, tmp_path: Path) -> Iterator[Any]:
    """A factory, because each test injects a DIFFERENT single fault."""
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    proxy_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"hrdru-{os.getpid()}"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    sessions: list[str] = []

    def build(*, fault: str) -> LiveProxiedTab:
        session = f"overseer-test-{os.getpid()}-{fault}"
        sessions.append(session)
        return _build(session=session, scratch=tmp_path, proxy_dir=proxy_dir, fault=fault)

    try:
        yield build
    finally:
        for session in sessions:
            _ = _cli(args=["--session", session, "server", "stop"])
            _ = _cli(args=["session", "delete", session])
        shutil.rmtree(proxy_dir, ignore_errors=True)


def _split_top(*, live: LiveProxiedTab) -> Any:
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return writer_module.HerdrWriter(timeout_seconds=10.0).split_window_top(
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
    """The real panes were exchanged; the reply describing it cannot be read."""
    live = faulted(fault=CORRUPT_SWAP)

    outcome = _split_top(live=live)

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

    outcome = _split_top(live=live)

    _assert_unresolved_but_landed(live=live, outcome=outcome)
    assert (
        live.state.methods().count("pane.layout") == 1
    ), "the withheld placement read must not be retried"
