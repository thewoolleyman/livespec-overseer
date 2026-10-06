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
polls the real `pane.process_info` until the server itself reports a foreground
group distinct from that pane's shell. Only then is the layout request
forwarded. So by the time the adapter takes its pre-launch reading, the pane is
occupied by a real child of a real shell, and the reading proving it comes from
herdr rather than from the surface under test.

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
OCCUPY_TIMEOUT = 20.0
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
    """What the forwarding proxy saw, and what it injected."""

    created: str = ""
    occupied: bool = False
    requests: list[dict[str, Any]] = field(default_factory=list)

    def adapter_writes(self) -> list[str]:
        """Every pane the ADAPTER sent input to — the proxy's own injection excluded.

        The injected `sleep` goes to the real server on a separate connection
        that never passes through the listener, so anything recorded here was
        written by the surface under test.
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


def _process_info(*, socket_path: str, pane_id: str) -> dict[str, Any]:
    reply = _raw_request(
        socket_path=socket_path, method="pane.process_info", params={"pane_id": pane_id}
    )
    info: dict[str, Any] = reply["result"]["process_info"]
    return info


def _is_occupied(*, info: dict[str, Any]) -> bool:
    return int(info["foreground_process_group_id"]) != int(info["shell_pid"])


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


def _occupy(*, socket_path: str, pane_id: str) -> None:
    """Start a REAL foreground child in `pane_id` and wait for herdr to report it."""
    _ = _raw_request(
        socket_path=socket_path,
        method="pane.send_input",
        params={"pane_id": pane_id, "text": OCCUPYING_COMMAND, "keys": ["Enter"]},
    )
    deadline = time.monotonic() + OCCUPY_TIMEOUT
    while time.monotonic() < deadline:
        if _is_occupied(info=_process_info(socket_path=socket_path, pane_id=pane_id)):
            return
        time.sleep(0.1)


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
    """Forward requests verbatim, occupying the created pane before the layout read."""
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
            if request["method"] == "pane.layout" and state.created and not state.occupied:
                _occupy(socket_path=real_socket, pane_id=state.created)
                state.occupied = True
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


def _build_tab(*, session: str, scratch: Path, proxy_dir: Path) -> LiveProxiedTab:
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
    threading.Thread(
        target=_serve_proxy,
        kwargs={"listener": listener, "real_socket": real_socket, "state": state},
        daemon=True,
    ).start()
    return LiveProxiedTab(
        real_socket=real_socket,
        proxy_socket=str(proxy_socket),
        original=original,
        unrelated=str(sibling["result"]["pane"]["pane_id"]),
        state=state,
    )


@pytest.fixture(name="live")
def _live(*, tmp_path: Path) -> Iterator[LiveProxiedTab]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-occupied"
    proxy_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"hrdrp-{os.getpid()}"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    built = _build_tab(session=session, scratch=tmp_path, proxy_dir=proxy_dir)
    try:
        yield built
    finally:
        _ = _cli(args=["--session", session, "server", "stop"])
        _ = _cli(args=["session", "delete", session])
        shutil.rmtree(proxy_dir, ignore_errors=True)


def _split_top(*, live: LiveProxiedTab) -> Any:
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return writer_module.HerdrWriter(timeout_seconds=30.0).split_window_top(
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


def test_a_really_occupied_new_pane_receives_no_command_or_enter_bytes(*, live: LiveProxiedTab):
    """THE native proof: a real child owns the new pane, so nothing is written to it.

    The adapter must issue no `pane.send_input` at all — that is the byte-level
    statement — and the created pane's own capture must not contain the command
    text, which is the statement read from the terminal itself.
    """
    outcome = _split_top(live=live)

    assert live.state.occupied is True, "the fixture must have really occupied the new pane"
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
    """
    outcome = _split_top(live=live)

    assert outcome.ok is False, "precondition: the launch was refused"
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert live.state.created in tops, "the created pane must survive the refusal"
    assert (
        tops[live.state.created] < tops[live.original]
    ), "the proven swap must not be undone or repeated"
    info = _process_info(socket_path=live.real_socket, pane_id=live.state.created)
    assert _is_occupied(info=info), "the occupying child must not be terminated"
    names = [str(entry.get("name")) for entry in info.get("foreground_processes", [])]
    assert OCCUPYING_NAME in names, info
    assert live.state.methods().count("pane.swap") == 1, live.state.methods()


def test_the_original_pane_and_its_unrelated_sibling_receive_nothing(*, live: LiveProxiedTab):
    """The supervised agent and the bystander must both come through untouched."""
    before = _geometry(socket_path=live.real_socket, pane_id=live.original)
    original_shell = int(
        _process_info(socket_path=live.real_socket, pane_id=live.original)["shell_pid"]
    )

    outcome = _split_top(live=live)

    assert outcome.ok is False, "precondition: the launch was refused"
    for pane_id in (live.original, live.unrelated):
        info = _process_info(socket_path=live.real_socket, pane_id=pane_id)
        assert not _is_occupied(info=info), f"{pane_id} was given something to run"
        assert DAEMON_COMMAND not in _capture(
            socket_path=live.real_socket, pane_id=pane_id
        ), f"the command text reached {pane_id}"
    after = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert after[live.unrelated] == before[live.unrelated], "the sibling moved"
    assert (
        int(_process_info(socket_path=live.real_socket, pane_id=live.original)["shell_pid"])
        == original_shell
    ), "the original pane's shell was replaced"
