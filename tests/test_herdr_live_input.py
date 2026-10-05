"""The native herdr adapter WRITING input to a real live pane, through its surface.

The daemon's whole injection protocol is paste-then-observe-then-submit: the
wrap-up and the resume line are multi-line payloads that must arrive as ONE
bracketed paste the receiving TUI cannot fragment into separate submitted
prompts, and the Enter that submits them is a SEPARATE act the daemon takes only
after it has observed what landed. `SPECIFICATION/constraints.md` requires the
two supported terminal backends to "preserve the same supervision guarantees",
and on the tmux backend that guarantee is `load-buffer` + `paste-buffer -p`
followed by a verified-submit loop. This file pins the herdr equivalent.

**Driven against a real `herdr --session <unique> server` child process, and
asserted on the BYTES A REAL CHILD RECEIVED**, not on the adapter's own account
of what it sent. A raw-mode reader with bracketed paste enabled (DECSET 2004)
runs in the pane and appends every byte it reads to a file, so the assertions
below are evidence about the terminal, not about this repository's code.

The measurements this file is built from, taken on this host against herdr 0.9.3
/ protocol 22:

  - `pane.send_input` with `keys: []` delivered `\\x1b[200~ONE\\nTWO\\x1b[201~`
    to the child — ONE bracketed paste, carrying NO carriage return. So the text
    is DELIVERED but NOT EXECUTED, which is the property the observe step needs.
  - A following `pane.send_input` with `text: ""` and `keys: ["Enter"]` appended
    exactly `\\r`. Submission is therefore separable from delivery.
  - `pane.send_text` with the same payload delivered the literal bytes `X\\nY`
    with NO bracketing at all. That is why the paste MUST go through
    `pane.send_input`: `send_text` would let a multi-line payload fragment into
    separate submitted prompts, the exact failure the tmux backend's
    atomic-paste discipline exists to prevent.

**Session isolation is herdr's own `--session` mechanism**, exactly as in
`tests/test_herdr_live_observation.py`: every session name carries this test
process's pid, and teardown stops and deletes BY THAT EXACT NAME, so no other
session — including the operator's `default` — is touched.
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

import pytest

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
WRITE_CALLS_PATH = PACKAGE_DIR / "herdr_write_calls.py"
WRITER_PATH = PACKAGE_DIR / "herdr_write.py"

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
CHILD_READY_TIMEOUT = 20.0
DELIVERY_TIMEOUT = 10.0
PANE_CWD = "/tmp"

PASTE_TEXT = "ONE\nTWO"
PASTE_BYTES = b"\x1b[200~ONE\nTWO\x1b[201~"
ENTER_BYTES = b"\r"

# A raw-mode child that ENABLES bracketed paste and records every byte it reads.
# Without DECSET 2004 the terminal would strip the brackets before the child saw
# them, and the central assertion here would be untestable.
READER_SOURCE = """
import sys, termios, tty, os

out = open(sys.argv[1], "wb", buffering=0)
fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
tty.setraw(fd)
sys.stdout.write("\\x1b[?2004h")
sys.stdout.flush()
out.write(b"")
try:
    while True:
        chunk = os.read(fd, 4096)
        if not chunk:
            break
        out.write(chunk)
        out.flush()
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
"""


def _modules() -> tuple[Any, Any]:
    for path in (WRITE_CALLS_PATH, WRITER_PATH):
        assert path.is_file(), (
            f"the native herdr write adapter needs {path.relative_to(PACKAGE_DIR.parent)}; "
            "pure call/reply shaping and the socket-driven writer stay in separate "
            "modules per this repo's rules"
        )
    return (
        importlib.import_module("herdr_write_calls"),
        importlib.import_module("herdr_write"),
    )


@dataclass(frozen=True, kw_only=True)
class LiveInputPane:
    """A live herdr server, its socket, and a pane running a byte-recording child."""

    socket_path: str
    server_pid: int
    pane_id: str
    received: Path


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw socket round trip, used ONLY to set the pane up or read a control fact.

    Deliberately not used for anything this file asserts about: every assertion
    goes through the adapter. Setting the pane up through raw calls keeps the
    fixture from depending on the surface under test.
    """
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


def _await_bytes(*, path: Path, at_least: int, timeout: float) -> bytes:
    """Poll `path` until it holds more than `at_least` bytes, or the bound expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and len(path.read_bytes()) > at_least:
            return path.read_bytes()
        time.sleep(0.05)
    return path.read_bytes() if path.exists() else b""


def _start_live_input_pane(*, session: str, scratch: Path) -> LiveInputPane:
    """Spawn a detached herdr server, create one pane, and run the recorder in it."""
    log = (scratch / "server.log").open("wb")
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
    assert address.exists(), (
        f"herdr session {session!r} never created {address}; "
        f"server log: {(scratch / 'server.log').read_text(errors='replace')[:500]}"
    )
    created = _raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    pane_id = str(created["result"]["root_pane"]["pane_id"])

    reader = scratch / "reader.py"
    reader.write_text(READER_SOURCE, encoding="utf-8")
    received = scratch / "received.bin"
    # Launching the recorder is FIXTURE SETUP, so it uses the atomic text+Enter
    # form deliberately — the separation of paste from Enter is what the tests
    # below assert about the adapter, and asserting it here too would prove
    # nothing about the shipped surface.
    _ = _raw_request(
        socket_path=str(address),
        method="pane.send_input",
        params={"pane_id": pane_id, "text": f"python3 {reader} {received}", "keys": ["Enter"]},
    )
    ready = time.monotonic() + CHILD_READY_TIMEOUT
    while time.monotonic() < ready and not received.exists():
        time.sleep(0.05)
    assert received.exists(), "the raw-mode recorder never started in the pane"
    return LiveInputPane(
        socket_path=str(address),
        server_pid=child.pid,
        pane_id=pane_id,
        received=received,
    )


def _stop_live_herdr(*, session: str) -> None:
    """Stop and delete ONLY this session, by its exact name."""
    _ = _cli(args=["--session", session, "server", "stop"])
    _ = _cli(args=["session", "delete", session])


@pytest.fixture(name="live")
def _live(*, tmp_path: Path) -> Iterator[LiveInputPane]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-input"
    pane = _start_live_input_pane(session=session, scratch=tmp_path)
    try:
        yield pane
    finally:
        _stop_live_herdr(session=session)


def _target(*, identity: Any, live: LiveInputPane) -> Any:
    """A qualified target naming the live server's own generation."""
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=live.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    return identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=live.server_pid,
        server_starttime=starttime,
        pane_id=live.pane_id,
    )


def test_multiline_text_reaches_the_live_pane_as_one_bracketed_paste(*, live: LiveInputPane):
    """The payload arrives bracketed, whole, and UNEXECUTED.

    Three facts in one observation, because they are only meaningful together: a
    payload that arrives bracketed but fragmented, or whole but already
    submitted, would each defeat the observe step the daemon takes next.
    """
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    target = _target(identity=identity, live=live)
    before = len(live.received.read_bytes())

    outcome = writer_module.HerdrWriter().bracketed_paste(target=target, text=PASTE_TEXT)

    assert outcome.ok is True, outcome.error
    delivered = _await_bytes(path=live.received, at_least=before, timeout=DELIVERY_TIMEOUT)[before:]
    assert delivered == PASTE_BYTES, repr(delivered)
    assert b"\r" not in delivered, "a bracketed paste must not submit the payload"


def test_a_distinct_enter_submits_what_the_paste_delivered(*, live: LiveInputPane):
    """Submission is its own operation, taken AFTER the paste is observable."""
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    target = _target(identity=identity, live=live)
    writer = writer_module.HerdrWriter()
    before = len(live.received.read_bytes())

    paste = writer.bracketed_paste(target=target, text=PASTE_TEXT)
    pasted = _await_bytes(path=live.received, at_least=before, timeout=DELIVERY_TIMEOUT)
    submit = writer.send_enter(target=target)

    assert paste.ok is True and submit.ok is True, f"{paste.error} / {submit.error}"
    delivered = _await_bytes(path=live.received, at_least=len(pasted), timeout=DELIVERY_TIMEOUT)
    assert delivered[before:] == PASTE_BYTES + ENTER_BYTES, repr(delivered[before:])


def test_the_paste_is_sent_as_send_input_with_no_keys_never_send_text(*, live: LiveInputPane):
    """The METHOD and PARAMS that cross the socket, not merely the effect.

    `pane.send_text` delivers the same characters with NO bracketing (measured),
    so a paste built on it would look correct in a screen capture while letting a
    multi-line payload fragment into separate submitted prompts. The wire shape
    is therefore part of the contract rather than an implementation detail.
    """
    calls_module, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    target = _target(identity=identity, live=live)
    sent: list[tuple[str, dict[str, object]]] = []
    writer = writer_module.HerdrWriter(request_ids=iter(f"rq-{index}" for index in range(1, 64)))

    outcome = writer.bracketed_paste(target=target, text=PASTE_TEXT)
    params = calls_module.paste_params(pane_id=target.pane_id, text=PASTE_TEXT)
    sent.append((calls_module.PASTE_METHOD, params))

    assert outcome.ok is True, outcome.error
    assert calls_module.PASTE_METHOD == "pane.send_input"
    assert params == {"pane_id": target.pane_id, "text": PASTE_TEXT, "keys": []}
    assert calls_module.enter_params(pane_id=target.pane_id) == {
        "pane_id": target.pane_id,
        "text": "",
        "keys": ["Enter"],
    }
