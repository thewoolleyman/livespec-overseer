"""TWO live herdr servers, both holding a pane called `w1:p1`, kept apart.

Herdr pane ids are unique only WITHIN a server (measured: a fresh server's root
pane is `w1:p1` every time), so the bare id an operator sees is ambiguous across
instances. `SPECIFICATION/contracts.md` requires a backend operation to identify
the actual backend INSTANCE as well as the target, and
`SPECIFICATION/constraints.md` requires instance identity to include the live
server generation. Those two rules exist for exactly the situation staged here.

**This is the live counterpart to `tests/test_herdr_pane_identity.py`.** That
file proves the ENCODING keeps two instances distinct — a pure, deterministic
property of the coordinate. It cannot prove that the ADAPTER actually routes by
that coordinate, because it never opens a socket. Here two REAL servers run at
once with deliberately different content in their identically-named panes, so a
read that went to the wrong instance returns the wrong text rather than merely
comparing unequal in a dataclass.

The failure this guards against is silent and plausible: an adapter that
remembered a generation, or that addressed panes by bare id, would answer every
question about `w1:p1` from whichever server happened to be reachable, and
every answer would look well-formed.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
MARKER_TIMEOUT = 15.0
PANE_CWD = "/tmp"

# Each server's pane prints a marker naming ITSELF, so a cross-read is visible
# as the wrong word rather than as an absence.
MARKERS = {"alpha": "OVSERVERALPHA", "beta": "OVSERVERBETA"}


@dataclass(frozen=True, kw_only=True)
class LiveServer:
    """One live herdr server child, its socket, its root pane and its marker."""

    name: str
    session: str
    socket_path: str
    server_pid: int
    pane_id: str
    marker: str


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw socket round trip, used ONLY to set a pane up or read a control fact."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(json.dumps({"id": "fixture", "method": method, "params": params}).encode() + b"\n")
    buffered = b""
    while b"\n" not in buffered:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buffered += chunk
    sock.close()
    parsed: dict[str, Any] = json.loads(buffered.split(b"\n")[0])
    return parsed


def _await_marker(*, server: LiveServer) -> None:
    """Wait until the pane's own marker is on screen, so a capture is meaningful."""
    deadline = time.monotonic() + MARKER_TIMEOUT
    while time.monotonic() < deadline:
        reply = _raw_request(
            socket_path=server.socket_path,
            method="pane.read",
            params={"pane_id": server.pane_id, "format": "text", "strip_ansi": True},
        )
        text = str(reply.get("result", {}).get("read", {}).get("text", ""))
        if server.marker in text:
            return
        time.sleep(0.1)


def _start_server(*, name: str, session: str, scratch: Path) -> LiveServer:
    """Spawn one detached herdr server and print this server's marker in its pane."""
    log = (scratch / f"{name}.log").open("wb")
    child = subprocess.Popen(  # noqa: S603 — the herdr CLI, not a Python child
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
    assert address.exists(), f"herdr session {session!r} never created {address}"
    created = _raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    server = LiveServer(
        name=name,
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        pane_id=str(created["result"]["root_pane"]["pane_id"]),
        marker=MARKERS[name],
    )
    _ = _raw_request(
        socket_path=server.socket_path,
        method="pane.send_input",
        params={
            "pane_id": server.pane_id,
            "text": f"printf '{server.marker}\\n'",
            "keys": ["Enter"],
        },
    )
    _await_marker(server=server)
    return server


@pytest.fixture(name="pair")
def _pair(*, tmp_path: Path) -> Iterator[tuple[LiveServer, LiveServer]]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    names = {
        "alpha": f"overseer-test-{os.getpid()}-alpha",
        "beta": f"overseer-test-{os.getpid()}-beta",
    }
    started: list[LiveServer] = []
    try:
        for name, session in names.items():
            started.append(_start_server(name=name, session=session, scratch=tmp_path))
        assert started[0].pane_id == started[1].pane_id, (
            "this test is only meaningful while both servers name their root pane "
            f"identically; got {started[0].pane_id} and {started[1].pane_id}"
        )
        yield (started[0], started[1])
    finally:
        for session in names.values():
            _ = _cli(args=["--session", session, "server", "stop"])
            _ = _cli(args=["session", "delete", session])


def _target(*, identity: Any, server: LiveServer) -> Any:
    starttime = claude_sessions.proc_starttime(pid=server.server_pid)
    assert starttime is not None, "a live herdr server must have a readable start time"
    return identity.HerdrPaneTarget(
        socket_path=server.socket_path,
        server_pid=server.server_pid,
        server_starttime=starttime,
        pane_id=server.pane_id,
    )


def _adapter() -> Any:
    return importlib.import_module("herdr_adapter").HerdrAdapter()


def test_each_server_s_identically_named_pane_reads_only_its_own_content(
    *, pair: tuple[LiveServer, LiveServer]
):
    """Same pane id, two live servers, two different answers — each the right one."""
    identity = importlib.import_module("herdr_identity")
    adapter = _adapter()
    alpha, beta = pair

    first = adapter.capture_pane(target=_target(identity=identity, server=alpha))
    second = adapter.capture_pane(target=_target(identity=identity, server=beta))

    assert first.ok is True and second.ok is True, f"{first.error} / {second.error}"
    assert alpha.marker in first.text, first.text[-300:]
    assert beta.marker not in first.text, "alpha's capture leaked beta's pane"
    assert beta.marker in second.text, second.text[-300:]
    assert alpha.marker not in second.text, "beta's capture leaked alpha's pane"


def test_each_server_s_identically_named_pane_reports_its_own_process(
    *, pair: tuple[LiveServer, LiveServer]
):
    """The foreground reading is per-INSTANCE too, not merely the capture."""
    identity = importlib.import_module("herdr_identity")
    adapter = _adapter()
    alpha, beta = pair

    first = adapter.foreground(target=_target(identity=identity, server=alpha))
    second = adapter.foreground(target=_target(identity=identity, server=beta))

    assert first.ok is True and second.ok is True, f"{first.error} / {second.error}"
    assert first.process.pane_id == second.process.pane_id == alpha.pane_id
    assert (
        first.process.shell_pid != second.process.shell_pid
    ), "two distinct servers must not report the same shell for the same pane id"


def test_a_coordinate_naming_the_other_server_s_generation_is_refused(
    *, pair: tuple[LiveServer, LiveServer]
):
    """The socket and the generation must agree, or nothing is read.

    Alpha's socket with BETA's process generation is a coordinate that could
    only arise from a stale or mixed-up record, and it is the shape that would
    silently adopt the wrong instance if the adapter trusted the path alone.
    """
    identity = importlib.import_module("herdr_identity")
    alpha, beta = pair
    beta_starttime = claude_sessions.proc_starttime(pid=beta.server_pid)
    assert beta_starttime is not None
    crossed = identity.HerdrPaneTarget(
        socket_path=alpha.socket_path,
        server_pid=beta.server_pid,
        server_starttime=beta_starttime,
        pane_id=alpha.pane_id,
    )

    outcome = _adapter().capture_pane(target=crossed)

    assert outcome.ok is False
    assert outcome.text == ""
    assert "generation" in outcome.error, outcome.error


def test_the_two_instances_carry_different_instance_keys(*, pair: tuple[LiveServer, LiveServer]):
    """The durable key a mapping store would hold distinguishes them as well.

    Asserted on LIVE servers rather than on constructed values, so the key is
    shown to separate instances that genuinely coexist.
    """
    identity = importlib.import_module("herdr_identity")
    alpha, beta = pair

    first = identity.herdr_instance_key(target=_target(identity=identity, server=alpha))
    second = identity.herdr_instance_key(target=_target(identity=identity, server=beta))

    assert first != second
    assert alpha.pane_id not in first, "an instance key must not embed the pane"
