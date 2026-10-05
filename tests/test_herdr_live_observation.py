"""The native herdr adapter OBSERVING a real live server, through its public surface.

This is the first slice of the native backend that is not pure parsing or raw
framing: `SPECIFICATION/constraints.md` requires the two supported terminal
backends to "preserve the same supervision guarantees", and the daemon's
observation surface is enumerate, capture and identify-the-foreground-process.
`SPECIFICATION/contracts.md` requires each backend operation to identify the
actual backend instance and target, so every call here is addressed by a
BACKEND-QUALIFIED target rather than by a bare pane id.

**Driven against a real `herdr --session <unique> server` child process, and
asserted through the ADAPTER rather than through raw JSON.** Raw socket probes
measured what the protocol does; they cannot show that the shipped adapter reads
it correctly, which is the only thing a caller depends on. The measurements this
file is built from, taken on this host against herdr 0.9.3 / protocol 22:

  - `SO_PEERCRED` on the session socket returns the pid of the spawned server
    child EXACTLY, so the generation the adapter binds is genuine process
    evidence rather than a fixture.
  - `pane.read` with `format=ansi, strip_ansi=false` retains a dim SGR verbatim
    (`\\x1b[2mOVDIM\\x1b[0m` round-tripped); with `format=text` no ESC survives.
    Dim styling is load-bearing elsewhere in this repo — it is what distinguishes
    a generated placeholder from typed input — so the default capture must keep
    it.
  - A NON-`exec` foreground child gets its own process group: `shell_pid` 143934
    against `foreground_process_group_id` 143978, with the foreground process
    reported as `sleep` and its cwd `/usr` while the shell had started in
    `/tmp`. So the foreground process and the foreground cwd are both readable,
    and both differ from the initial shell — which is exactly why the adapter
    must report the foreground rather than the shell.
  - A pane id absent from that server answers with an `error` envelope
    (`pane_not_found`), never an empty success.

**Session isolation is herdr's own `--session` mechanism**, which is what herdr
documents: each named session owns its directory and socket under the normal
config root. No `HOME`, `XDG_*` or `*_HOME` variable is repurposed — herdr 0.9.3
ignores `XDG_CONFIG_HOME` anyway (measured), so overriding it would isolate
nothing while making the test lie about how it is isolated. Every session this
file creates carries a unique name including the test process's pid, and teardown
stops and deletes BY THAT EXACT NAME, so no other session — including the
operator's `default` — is touched.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import struct
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
CALLS_PATH = PACKAGE_DIR / "herdr_calls.py"
ADAPTER_PATH = PACKAGE_DIR / "herdr_adapter.py"

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
# The pane is created in /tmp and the sentinel child then moves to /usr, so a
# reading that reports the SHELL's cwd and one that reports the FOREGROUND cwd
# are distinguishable rather than coincidentally equal.
PANE_CWD = "/tmp"
SENTINEL_CWD = "/usr"
SENTINEL_COMMAND = f"cd {SENTINEL_CWD} && sleep 120"
SENTINEL_NAME = "sleep"
DIM_MARKER = "OVDIM"
DIM_BYTES = f"\x1b[2m{DIM_MARKER}\x1b[0m"
DIM_COMMAND = r"printf '\033[2m" + DIM_MARKER + r"\033[0m\n'"


def _modules() -> tuple[Any, Any]:
    for path in (CALLS_PATH, ADAPTER_PATH):
        assert path.is_file(), (
            f"the native herdr observation adapter needs "
            f"{path.relative_to(PACKAGE_DIR.parent)}; pure call/reply shaping and the "
            "socket-driven adapter stay in separate modules per this repo's rules"
        )
    return (
        importlib.import_module("herdr_calls"),
        importlib.import_module("herdr_adapter"),
    )


@dataclass(frozen=True, kw_only=True)
class LiveHerdr:
    """One live herdr server child, its socket, and its root pane."""

    session: str
    socket_path: str
    server_pid: int
    pane_id: str


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw socket round trip, used ONLY to set a pane up or read a control fact.

    Deliberately not used for anything this file asserts about: the assertions go
    through the adapter. Setting the pane up through raw calls keeps the fixture
    from depending on the surface under test.
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


def _peer_pid_of(*, socket_path: str) -> int:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    sock.close()
    pid, _uid, _gid = struct.unpack("3i", raw)
    return pid


def _start_live_herdr(*, session: str, scratch: Path) -> LiveHerdr:
    """Spawn a detached `herdr --session <session> server` and create one pane.

    `herdr server` is a FOREGROUND persistent process with no detach flag
    (measured: it does not self-daemonize, and no client command auto-starts it),
    so the test owns it as a child in its own process group and stops it by name
    in teardown.
    """
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
    return LiveHerdr(
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        pane_id=str(created["result"]["root_pane"]["pane_id"]),
    )


def _stop_live_herdr(*, session: str) -> None:
    """Stop and delete ONLY this session, by its exact name."""
    _ = _cli(args=["--session", session, "server", "stop"])
    _ = _cli(args=["session", "delete", session])


@pytest.fixture(name="live")
def _live(*, tmp_path: Path) -> Iterator[LiveHerdr]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-observe"
    server = _start_live_herdr(session=session, scratch=tmp_path)
    try:
        yield server
    finally:
        _stop_live_herdr(session=session)


def _run_in_pane(*, live: LiveHerdr, command: str) -> None:
    reply = _raw_request(
        socket_path=live.socket_path,
        method="pane.send_input",
        params={"pane_id": live.pane_id, "text": command, "keys": ["Enter"]},
    )
    assert "result" in reply, f"fixture command {command!r} was refused: {reply}"


def test_the_adapter_identifies_the_live_server_generation_it_is_speaking_to(*, live: LiveHerdr):
    """Identification must yield the real server process, not the socket path alone.

    `SPECIFICATION/constraints.md`: instance identity "MUST include the live
    server generation, proven by its process identity and start time". The
    spawned child's pid is known independently here, so this asserts the adapter
    learned the TRUE generation rather than something self-consistent.
    """
    _calls, adapter_module = _modules()
    adapter = adapter_module.HerdrAdapter()

    identified = adapter.identify(socket_path=live.socket_path)

    assert identified.ok is True, identified.error
    assert identified.peer is not None
    assert identified.peer.pid == live.server_pid, (
        "the adapter must bind the generation of the server actually listening; "
        f"peercred independently reports {_peer_pid_of(socket_path=live.socket_path)}"
    )
    assert identified.peer.uid == os.getuid()
    assert identified.peer.starttime, "a generation needs the non-reusable half too"


def test_the_adapter_enumerates_the_exact_panes_of_the_selected_server(*, live: LiveHerdr):
    """Enumeration is of ONE addressed server, and reports exact identifiers."""
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    adapter = adapter_module.HerdrAdapter()
    identified = adapter.identify(socket_path=live.socket_path)
    assert identified.ok is True, identified.error
    target = identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=identified.peer.pid,
        server_starttime=identified.peer.starttime,
        pane_id=live.pane_id,
    )

    listing = adapter.list_panes(target=target)

    assert listing.ok is True, listing.error
    found = [row for row in listing.panes if row.pane_id == live.pane_id]
    assert len(found) == 1, f"the created pane must appear exactly once: {listing.panes}"
    row = found[0]
    assert row.workspace_id, "a row carries its workspace id"
    assert row.tab_id.startswith(
        row.workspace_id
    ), f"a herdr tab id is workspace-scoped: {row.tab_id!r} under {row.workspace_id!r}"
    assert row.focused is True, "the only pane of the only workspace is focused"


def test_the_default_capture_is_visible_pane_content_that_retains_ansi(*, live: LiveHerdr):
    """The default capture keeps styling, because this repo's input gates read it.

    A dim SGR is what distinguishes a generated placeholder from typed input, so
    a capture that strips it would make an occupied pane look idle. The plain
    reading is asserted alongside to prove the ANSI is really being retained
    rather than merely absent from a stripped stream.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    adapter = adapter_module.HerdrAdapter()
    identified = adapter.identify(socket_path=live.socket_path)
    assert identified.ok is True, identified.error
    target = identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=identified.peer.pid,
        server_starttime=identified.peer.starttime,
        pane_id=live.pane_id,
    )
    _run_in_pane(live=live, command=DIM_COMMAND)

    deadline = time.monotonic() + 15.0
    capture = adapter.capture_pane(target=target)
    while time.monotonic() < deadline and DIM_BYTES not in capture.text:
        time.sleep(0.25)
        capture = adapter.capture_pane(target=target)

    assert capture.ok is True, capture.error
    assert (
        DIM_BYTES in capture.text
    ), f"the dim SGR must survive the default capture; got {capture.text[-160:]!r}"
    stripped = adapter.capture_pane(target=target, retain_ansi=False)
    assert stripped.ok is True, stripped.error
    assert DIM_MARKER in stripped.text, "the stripped reading still carries the text"
    assert "\x1b" not in stripped.text, "the stripped reading carries no escapes"


def test_the_adapter_reports_the_actual_foreground_process_not_the_pane_shell(*, live: LiveHerdr):
    """A foreground child must be reported as itself, with ITS cwd, not the shell's.

    The sentinel is launched WITHOUT `exec`, so it occupies its own process group
    while the pane's root shell survives — the state the daemon has to read
    correctly to tell a busy pane from an idle one. It also `cd`s first, so the
    foreground cwd differs from the cwd the pane was created in and the two
    readings cannot be confused.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    adapter = adapter_module.HerdrAdapter()
    identified = adapter.identify(socket_path=live.socket_path)
    assert identified.ok is True, identified.error
    target = identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=identified.peer.pid,
        server_starttime=identified.peer.starttime,
        pane_id=live.pane_id,
    )
    at_prompt = adapter.foreground(target=target)
    assert at_prompt.ok is True, at_prompt.error
    shell_pid = at_prompt.process.shell_pid
    assert shell_pid > 0

    _run_in_pane(live=live, command=SENTINEL_COMMAND)
    deadline = time.monotonic() + 20.0
    reading = adapter.foreground(target=target)
    while time.monotonic() < deadline and reading.ok and reading.process.name != SENTINEL_NAME:
        time.sleep(0.25)
        reading = adapter.foreground(target=target)

    assert reading.ok is True, reading.error
    assert (
        reading.process.name == SENTINEL_NAME
    ), f"the foreground process must be the live child, got {reading.process!r}"
    assert reading.process.shell_pid == shell_pid, "the pane's root shell survives"
    assert reading.process.process_group_id != shell_pid, (
        "a non-exec child owns its own process group; equality here would mean the "
        "shell itself is in the foreground, which is the idle reading"
    )
    assert reading.process.cwd == SENTINEL_CWD, (
        f"the FOREGROUND cwd is wanted, not the shell's {PANE_CWD!r}: " f"{reading.process.cwd!r}"
    )


def test_a_pane_absent_from_the_addressed_server_fails_closed(*, live: LiveHerdr):
    """An unknown pane yields a named refusal and no data, on every read.

    `SPECIFICATION/contracts.md` forbids reading an unusable backend response as
    "proof of an idle pane", and a pane the server does not have is the clearest
    case: herdr answers with an `error` envelope, which must not become an empty
    capture or a zero-pid process.
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    adapter = adapter_module.HerdrAdapter()
    identified = adapter.identify(socket_path=live.socket_path)
    assert identified.ok is True, identified.error
    absent = identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=identified.peer.pid,
        server_starttime=identified.peer.starttime,
        pane_id="w9:p9",
    )

    capture = adapter.capture_pane(target=absent)
    reading = adapter.foreground(target=absent)

    assert capture.ok is False and capture.text == "", "an absent pane is not an empty pane"
    assert capture.error != ""
    assert reading.ok is False and reading.process is None
    assert reading.error != ""


def test_a_changed_server_generation_is_refused_on_every_observation(*, live: LiveHerdr):
    """A target pinned to another generation must not read the pane that is there.

    Same socket, same pane id, a start time that is not this server's: the
    coordinate names a generation that no longer listens, and
    `SPECIFICATION/scenarios.md` requires that "reusing a socket path or pane id
    after a server restart does not reproduce the former instance identity".
    """
    _calls, adapter_module = _modules()
    identity = importlib.import_module("herdr_identity")
    adapter = adapter_module.HerdrAdapter()
    identified = adapter.identify(socket_path=live.socket_path)
    assert identified.ok is True, identified.error
    stale = identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=identified.peer.pid,
        server_starttime=identified.peer.starttime + "9",
        pane_id=live.pane_id,
    )

    for name, outcome in (
        ("capture", adapter.capture_pane(target=stale)),
        ("foreground", adapter.foreground(target=stale)),
        ("list", adapter.list_panes(target=stale)),
    ):
        assert outcome.ok is False, f"{name} accepted a foreign server generation"
        assert "generation" in outcome.error, f"{name}: {outcome.error}"
