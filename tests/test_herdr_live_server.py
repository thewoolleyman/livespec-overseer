"""The shared live-herdr server helper waits for a REQUEST, never for a path.

The defect these controls pin, measured 2026-10-12: every live module spawned
`herdr --session <name> server`, waited only for the socket PATH to exist, then
connected once. A Unix socket path exists from `bind()`, before `listen()`, so under
full-suite load that connect was refused (`ECONNREFUSED`, observed in a full
pre-push run in
`tests/test_herdr_live_observation.py::test_the_adapter_reports_the_actual_foreground_process_not_the_pane_shell[True]`).
And fixed session names reused across cases let a PREVIOUS server's leftover path
satisfy the wait before the new server had even bound.

**The timing here is CONTROLLED, not raced.** A disclosed stand-in server (a short
Python program installed as `herdr` on a private `PATH`, under a private `HOME`) binds
its socket and then WAITS FOR A GATE FILE before it listens, or before it replaces a
stale path. The gate is opened from inside the readiness wait's own `sleep`, after
the test has itself observed that an early connect is refused at that instant. So
"published before accepting" and "a stale path left by a prior server" are states
the test holds open on purpose, not windows it hopes to land in.

The stand-in also lets every branch of `tests/herdr_live_server.py` run on a host with
no real herdr (CI), where the live modules skip. On a herdr host the same helper is
exercised for real by the nine live modules.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import herdr_live_server
import pytest
from herdr_alias_fixture_identity import unix_socket_path_capacity
from herdr_live_server import (
    ReadyPoll,
    await_server_ready,
    create_workspace,
    herdr_cli,
    live_session_names,
    probe_ready,
    raw_request,
    require_herdr,
    session_socket,
    start_server,
    stop_server,
    unique_session,
)

__all__: list[str] = []

GATE_TIMEOUT = 10.0

# The stand-in `herdr`. Only the CLI shapes the helper uses are implemented, and the
# server answers `ping` and `workspace.create` the way herdr 0.9.3 does. Its startup
# is steered by two environment variables so a control can hold one state open:
#   FAKE_HERDR_MODE  listen-late   bind, then wait for the gate, then listen
#                    replace-stale wait for the gate, then unlink the stale path, bind, listen
#                    exit          print one line and exit 7 without binding
#   FAKE_HERDR_GATE  the gate file those modes wait for
_FAKE_HERDR = """#!{python}
import json, os, shutil, signal, socket, sys, time
from pathlib import Path

args = sys.argv[1:]
root = Path(os.environ["HOME"]) / ".config" / "herdr" / "sessions"


def wait_gate():
    gate = Path(os.environ["FAKE_HERDR_GATE"])
    deadline = time.monotonic() + 30
    while not gate.exists():
        if time.monotonic() > deadline:
            sys.exit("fake herdr: gate never opened")
        time.sleep(0.005)


def serve(session):
    home = root / session
    home.mkdir(parents=True, exist_ok=True)
    path = home / "herdr.sock"
    mode = os.environ.get("FAKE_HERDR_MODE", "")
    if mode == "exit":
        print("fake herdr: refusing to start", flush=True)
        sys.exit(7)
    if mode == "replace-stale":
        wait_gate()
        path.unlink()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    (home / "server.pid").write_text(str(os.getpid()))
    if mode == "listen-late":
        wait_gate()
    listener.listen(8)

    def stop(*_):
        path.unlink(missing_ok=True)
        os._exit(0)

    signal.signal(signal.SIGTERM, stop)
    workspaces = 0
    while True:
        conn, _ = listener.accept()
        with conn:
            data = b""
            while b"\\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                continue
            request = json.loads(data)
            if request["method"] == "ping":
                reply = {{"id": request["id"], "result": {{"type": "pong"}}}}
            elif request["method"] == "workspace.create":
                workspaces += 1
                pane = {{"pane_id": f"w{{workspaces}}:p1"}}
                reply = {{"id": request["id"], "result": {{"root_pane": pane}}}}
            else:
                reply = {{"id": request["id"], "error": {{"code": "unknown_method"}}}}
            conn.sendall(json.dumps(reply).encode() + b"\\n")


if args[:1] == ["--session"]:
    session, rest = args[1], args[2:]
    if rest == ["server"]:
        serve(session)
    if rest == ["server", "stop"]:
        pid_file = root / session / "server.pid"
        if not pid_file.exists():
            sys.exit("server is not running")
        os.kill(int(pid_file.read_text()), signal.SIGTERM)
        deadline = time.monotonic() + 10
        while (root / session / "herdr.sock").exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        pid_file.unlink()
elif args[:2] == ["session", "delete"]:
    shutil.rmtree(root / args[2], ignore_errors=True)
    print("deleted session", args[2])
elif args[:2] == ["session", "list"]:
    names = sorted(p.name for p in root.iterdir()) if root.exists() else []
    print(json.dumps({{"sessions": [{{"name": name}} for name in names]}}))
else:
    sys.exit(f"fake herdr: unsupported {{args!r}}")
"""


@dataclass(kw_only=True)
class _FakeHost:
    """A private HOME and a PATH whose `herdr` is the disclosed stand-in."""

    home: Path
    gate: Path


@pytest.fixture(name="fake_host")
def _fake_host(*, monkeypatch: pytest.MonkeyPatch) -> Iterator[_FakeHost]:
    # A SHORT root, so the session's socket paths fit `sun_path` (~108 bytes).
    root = Path(tempfile.mkdtemp(prefix="hls"))
    bin_dir = root / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "herdr"
    _ = fake.write_text(_FAKE_HERDR.format(python=sys.executable), encoding="utf-8")
    fake.chmod(0o755)
    home = root / "h"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    host = _FakeHost(home=home, gate=root / "gate")
    monkeypatch.setenv("FAKE_HERDR_GATE", str(host.gate))
    try:
        yield host
    finally:
        sessions = host.home / ".config" / "herdr" / "sessions"
        for session in sessions.iterdir() if sessions.exists() else ():
            stop_server(session=session.name)
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(name="short_dir")
def _short_dir() -> Iterator[Path]:
    """A directory short enough for an AF_UNIX path, removed afterwards."""
    root = Path(tempfile.mkdtemp(prefix="hls"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _connect_refused(*, path: Path) -> bool:
    """Whether an EARLY single connect — the old fixtures' move — is refused right now."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        try:
            sock.connect(str(path))
        except ConnectionRefusedError:
            return True
    return False


@dataclass(kw_only=True)
class _GateOpener:
    """The readiness wait's `sleep`: on its FIRST call, witness the held state, then open.

    What it witnesses is recorded, so the test can assert that at the moment the
    helper declined to proceed, an early connect really was being refused.
    """

    gate: Path
    path: Path
    witnessed: list[str] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        if not self.gate.exists():
            deadline = time.monotonic() + GATE_TIMEOUT
            while not self.path.exists():
                assert time.monotonic() < deadline, f"{self.path} was never published"
                time.sleep(0.005)
            self.witnessed.append(
                "early connect refused" if _connect_refused(path=self.path) else "accepted"
            )
            self.gate.touch()
        time.sleep(seconds)


def _stale_socket(*, path: Path) -> None:
    """A socket path a PRIOR server bound and never removed: present, nobody listening."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as prior:
        prior.bind(str(path))
    assert path.exists() and _connect_refused(path=path), "control precondition: a stale path"


def test_a_path_published_before_the_listener_accepts_is_waited_out(
    *, fake_host: _FakeHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path exists and refuses connections; the helper keeps waiting, then proves ready."""
    monkeypatch.setenv("FAKE_HERDR_MODE", "listen-late")
    session = unique_session(label="listen-late")
    opener = _GateOpener(gate=fake_host.gate, path=session_socket(session=session))

    server = start_server(
        scratch=tmp_path, session=session, poll=ReadyPoll(seconds=GATE_TIMEOUT, sleep=opener)
    )

    assert opener.witnessed == ["early connect refused"], opener.witnessed
    assert server.readiness.attempts >= 2, "the first probe must not have been accepted"
    assert server.readiness.peer_pid == server.server_pid
    assert server.readiness.reply["result"] == {"type": "pong"}, server.readiness.reply
    assert server.log_path == tmp_path / f"{session}.log"
    stop_server(session=session)
    assert not session_socket(session=session).exists()


def test_a_stale_path_from_a_prior_server_never_counts_as_this_server(
    *, fake_host: _FakeHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leftover path satisfied the old wait before the new server had even bound."""
    monkeypatch.setenv("FAKE_HERDR_MODE", "replace-stale")
    session = unique_session(label="stale")
    address = session_socket(session=session)
    _stale_socket(path=address)
    opener = _GateOpener(gate=fake_host.gate, path=address)

    server = start_server(
        scratch=tmp_path,
        session=session,
        log_name="stale.log",
        poll=ReadyPoll(seconds=GATE_TIMEOUT, sleep=opener),
    )

    assert opener.witnessed == ["early connect refused"], opener.witnessed
    assert server.readiness.attempts >= 2
    assert server.readiness.peer_pid == server.server_pid
    assert server.log_path == tmp_path / "stale.log"
    assert create_workspace(socket_path=server.socket_path, label=session, cwd="/tmp") == "w1:p1"
    assert session in live_session_names()
    stop_server(session=session)
    assert session not in live_session_names()


def _frozen(*, ticks: list[float]) -> ReadyPoll:
    remaining = list(ticks)
    return ReadyPoll(
        seconds=1.0,
        monotonic=lambda: remaining.pop(0) if remaining else 1e9,
        sleep=lambda _seconds: None,
    )


@pytest.fixture(name="idle_child")
def _idle_child() -> Iterator[subprocess.Popen[bytes]]:
    """A live process that never binds anything: the owned server that never starts."""
    sleep = shutil.which("sleep")
    assert sleep is not None, "control precondition: a `sleep` binary"
    child = subprocess.Popen([sleep, "60"])  # noqa: S603 — a plain sleeping process
    try:
        yield child
    finally:
        child.kill()
        _ = child.wait()


def test_a_stale_path_held_by_a_rival_live_listener_is_refused_at_the_bound(
    *, tmp_path: Path, short_dir: Path, idle_child: subprocess.Popen[bytes]
) -> None:
    """Something IS accepting at the path — just not the server this test spawned."""
    address = short_dir / "herdr.sock"
    log_path = tmp_path / "server.log"
    _ = log_path.write_text("rival-control log line\n", encoding="utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as rival:
        rival.bind(str(address))
        rival.listen(8)
        with pytest.raises(AssertionError) as refused:
            _ = await_server_ready(
                socket_path=address,
                session="rival-control",
                child=idle_child,
                log_path=log_path,
                poll=_frozen(ticks=[0.0, 0.0, 2.0]),
            )
        conn, _ = rival.accept()
        with conn:
            conn.settimeout(1.0)
            transmitted = conn.recv(1)

    message = str(refused.value)
    assert f"belongs to pid {os.getpid()}, not the owned server pid {idle_child.pid}" in message
    assert "never answered a 'ping' request" in message, message
    assert "within 1.0s after 1 attempts" in message, message
    assert "rival-control log line" in message, message
    assert transmitted == b"", "nothing may be sent to a listener that is not the owned server"


def test_a_path_that_never_appears_fails_naming_that_condition(
    *, tmp_path: Path, idle_child: subprocess.Popen[bytes]
) -> None:
    log_path = tmp_path / "empty.log"
    log_path.touch()
    with pytest.raises(AssertionError) as refused:
        _ = await_server_ready(
            socket_path=tmp_path / "never.sock",
            session="never-published",
            child=idle_child,
            log_path=log_path,
            poll=_frozen(ticks=[0.0, 0.0, 2.0]),
        )

    message = str(refused.value)
    assert f"socket path {tmp_path / 'never.sock'} does not exist" in message, message
    assert "<server log empty>" in message, message


def test_an_owned_server_that_exits_is_reported_as_an_exit_not_a_timeout(
    *, fake_host: _FakeHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real start path, with a server that exits; its session is still cleaned up."""
    del fake_host
    monkeypatch.setenv("FAKE_HERDR_MODE", "exit")
    session = unique_session(label="exits")

    with pytest.raises(AssertionError) as refused:
        _ = start_server(scratch=tmp_path, session=session)

    message = str(refused.value)
    assert "exited with status 7" in message, message
    assert "fake herdr: refusing to start" in message, message
    assert session not in live_session_names()


def test_an_unreadable_log_is_named_rather_than_raised(
    *, tmp_path: Path, idle_child: subprocess.Popen[bytes]
) -> None:
    with pytest.raises(AssertionError) as refused:
        _ = await_server_ready(
            socket_path=tmp_path / "never.sock",
            session="no-log",
            child=idle_child,
            log_path=tmp_path / "absent.log",
            poll=_frozen(ticks=[0.0, 2.0]),
        )

    message = str(refused.value)
    assert "<server log unreadable" in message, message
    assert "after 0 attempts" in message and "no readiness probe was attempted" in message


def _answer_once(*, path: Path, answer: bytes) -> threading.Thread:
    """A listener in THIS process that reads one request and answers `answer` verbatim."""
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    listener.listen(1)

    def serve() -> None:
        with listener:
            conn, _ = listener.accept()
            with conn:
                _ = conn.recv(65536)
                conn.sendall(answer)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (b"not json\n", "'ping' got no JSON reply: b'not json\\n'"),
        (b"", "'ping' got no JSON reply: b''"),
        (b'{"id": "fixture", "error": {"code": "busy"}}\n', "'ping' was not answered successfully"),
        (b"[1]\n", "'ping' was not answered successfully: [1]"),
    ],
)
def test_an_answer_that_is_not_a_successful_reply_is_not_readiness(
    *, short_dir: Path, answer: bytes, expected: str
) -> None:
    """A listener owned by the expected pid must still ANSWER the request successfully."""
    path = short_dir / "herdr.sock"
    thread = _answer_once(path=path, answer=answer)

    reason, peer, reply = probe_ready(socket_path=path, expected_pid=os.getpid())
    thread.join(timeout=5.0)

    assert expected in reason, reason
    assert peer == os.getpid()
    assert reply == {}


def test_a_raw_request_closed_without_an_answer_reads_as_empty(*, short_dir: Path) -> None:
    path = short_dir / "herdr.sock"
    thread = _answer_once(path=path, answer=b"")

    reply = raw_request(socket_path=str(path), method="pane.list", params={})
    thread.join(timeout=5.0)

    assert reply == {}


def test_session_names_are_unique_per_call_and_fit_the_socket_budget() -> None:
    names = {unique_session(label="same") for _ in range(50)}
    assert len(names) == 50, "every call must mint a distinct session"
    assert all(f"-{os.getpid()}-" in name for name in names)
    assert unique_session(label="").startswith("ov-live-")
    assert unique_session(label="a.b/c d").startswith("ov-a-b-c-d-")
    longest = unique_session(label="x" * 200)
    client = session_socket(session=longest).with_name("herdr-client.sock")
    assert len(os.fsencode(client)) < unix_socket_path_capacity(), client


def test_the_cli_refuses_any_call_that_would_address_the_default_server() -> None:
    with pytest.raises(AssertionError, match="would address the default server"):
        _ = herdr_cli(args=["workspace", "list"])


def test_a_host_without_herdr_skips_and_has_nothing_to_stop(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert herdr_live_server.herdr_installed() is False
    stop_server(session=unique_session(label="absent"))
    with pytest.raises(pytest.skip.Exception, match="herdr is not installed"):
        require_herdr()


def test_the_server_child_never_inherits_the_operator_socket_variable(
    *, fake_host: _FakeHost, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del fake_host
    monkeypatch.setenv("HERDR_SOCKET_PATH", "/operator/herdr.sock")
    explicit = {**os.environ, "HERDR_SOCKET_PATH": "/operator/herdr.sock"}

    for env in (None, explicit):
        server = start_server(scratch=tmp_path, label="env", env=env)
        environ = Path(f"/proc/{server.server_pid}/environ").read_bytes().split(b"\0")
        stop_server(session=server.session)
        assert not any(entry.startswith(b"HERDR_SOCKET_PATH=") for entry in environ)
        assert server.session.startswith("ov-env-")
