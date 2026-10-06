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

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
# A liveness floor, not a latency budget. This was briefly raised to 120.0 on a
# diagnosis that did not hold up — the clean control's failures were traced to
# its wait PREDICATE, not to this bound (see `_await_foreground`), so the raise
# is backed out rather than left behind as a fix for something else.
LAUNCH_TIMEOUT = 20.0
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


def _process_info(*, socket_path: str, pane_id: str) -> dict[str, Any]:
    reply = _raw_request(
        socket_path=socket_path, method="pane.process_info", params={"pane_id": pane_id}
    )
    info: dict[str, Any] = reply["result"]["process_info"]
    return info


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = _raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _await_foreground(*, socket_path: str, pane_id: str, name: str) -> dict[str, Any]:
    """Poll until `name` IS the pane's foreground process, or the bound expires.

    Waiting on the NAME rather than on the first foreground-group change is
    load-bearing rather than tidiness, and this file used to get it wrong. A
    shell runs a command by FORKING and then `exec`ing, so there is a real
    window in which the foreground group has already left the shell while the
    child is still `bash`. Measured on this host with an otherwise idle server,
    the first observed group change was `bash` rather than the command on 4 of
    12 deliveries. A loop that stopped at that first change and then demanded
    the command's name failed inside that window; this one keeps looking until
    the intended runtime is actually there, and still fails if the bound expires.
    """
    deadline = time.monotonic() + LAUNCH_TIMEOUT
    info = _process_info(socket_path=socket_path, pane_id=pane_id)
    while time.monotonic() < deadline:
        info = _process_info(socket_path=socket_path, pane_id=pane_id)
        if any(str(entry.get("name")) == name for entry in info.get("foreground_processes", [])):
            return info
        time.sleep(0.1)
    return info


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
    """Relay verbatim, except for a swap this proxy answers with a decline."""
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


def _build(*, session: str, scratch: Path, proxy_dir: Path, decline: bool) -> LiveProxiedTab:
    real_socket = _start_server(session=session, scratch=scratch, log_name=f"{session}.log")
    created = _raw_request(
        socket_path=real_socket,
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    state = ProxyState(decline=decline)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    proxy_socket = proxy_dir / f"{'decline' if decline else 'clean'}.sock"
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
        original=str(created["result"]["root_pane"]["pane_id"]),
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

    def build(*, decline: bool) -> LiveProxiedTab:
        session = f"overseer-test-{os.getpid()}-{'decline' if decline else 'clean'}"
        sessions.append(session)
        return _build(session=session, scratch=tmp_path, proxy_dir=proxy_dir, decline=decline)

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


def test_a_declined_swap_leaves_a_real_unmoved_pane_and_writes_nothing(*, proxied: Any):
    """The known partial layout, read from the real terminal rather than claimed.

    The split landed, so there is a pane; the swap did not, so it is still below
    the target; and because that whole state was observed, the outcome is
    CERTAIN while still naming the pane an operator has to deal with.
    """
    live = proxied(decline=True)

    outcome = _split_top(live=live)

    assert live.state.declined is True, "the decline was never actually injected"
    assert outcome.ok is False, "a declined swap is not a completed layout change"
    assert outcome.pane_id == live.state.created, "the created pane must still be named"
    assert outcome.effect_unknown is False, f"a legible decline is certain: {outcome.error}"
    assert DECLINE_REASON in outcome.error, outcome.error
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert live.state.created in tops, f"the real split must have landed: {tops}"
    assert (
        tops[live.state.created] > tops[live.original]
    ), f"the pane must really be BELOW the target, which is what was declined: {tops}"
    assert live.state.writes() == [], "the command was delivered after a declined swap"
    for pane_id in (live.state.created, live.original):
        info = _process_info(socket_path=live.real_socket, pane_id=pane_id)
        assert int(info["foreground_process_group_id"]) == int(
            info["shell_pid"]
        ), f"{pane_id} was given something to run: {info}"
        assert MARKER not in _capture(
            socket_path=live.real_socket, pane_id=pane_id
        ), f"the command text reached {pane_id}"


def test_the_same_harness_without_the_decline_still_launches(*, proxied: Any):
    """The control that makes the test above mean something.

    Identical proxy, identical real server, one flag different: here the swap is
    relayed and really lands, so the pane ends up above the target with the
    command running in its own retained shell.
    """
    live = proxied(decline=False)

    outcome = _split_top(live=live)

    assert live.state.declined is False, "the control must inject nothing"
    assert outcome.ok is True, outcome.error
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert tops[outcome.pane_id] < tops[live.original], f"the swap must have landed: {tops}"
    info = _await_foreground(
        socket_path=live.real_socket, pane_id=outcome.pane_id, name=LAUNCH_NAME
    )
    names = [str(entry.get("name")) for entry in info.get("foreground_processes", [])]
    assert LAUNCH_NAME in names, info
    assert int(info["shell_pid"]) > 0, "the retained shell must survive the launch"
    assert int(info["foreground_process_group_id"]) != int(
        info["shell_pid"]
    ), "the command must run UNDER the retained shell, not replace it"
    assert live.state.writes() == [outcome.pane_id], live.state.writes()
