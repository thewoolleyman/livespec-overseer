"""The ONE owned, request-proven herdr server the live test tier starts and stops.

Every live herdr module used to carry its own copy of the same start sequence:
spawn `herdr --session <name> server`, wait for the socket PATH to exist, then
connect once. A Unix socket path exists from `bind()`, BEFORE `listen()`, so under
full-suite load that single connect was refused (`ECONNREFUSED`, observed in a full
pre-push run). And because the session names were fixed per module
(`overseer-test-<pid>-observe`, reused across parametrized cases), a previous case's
leftover path could satisfy the wait before the new server had even bound. PR #2382
(`overseer-btem3k`) fixed that race in one module by proving the listener's
`SO_PEERCRED` pid; this module is that approach, shared, and made stricter.

**Readiness is a SUCCESSFUL REQUEST, never a path.** :func:`await_server_ready`
returns only after one connection whose `SO_PEERCRED` pid is the spawned child's
own pid has answered a `ping` with a `result` envelope. A missing path, a refused
connect, a listener owned by any other process, a closed connection and a refusal
envelope are all just "not yet", retried until the bound; then the failure names
the last condition that never held and carries the server log. The owned child
exiting first is reported as an exit, not as a timeout.

**Isolation is herdr's own `--session` mechanism.** Every session name is unique per
call (pid plus a random suffix), every CLI call names `--session <unique>` or is a
`session ...` subcommand, and :func:`stop_server` stops and deletes BY THAT EXACT
NAME and then verifies the session is really gone. The operator's default server is
never addressed. The server child never inherits `HERDR_SOCKET_PATH`, so a server
started outside a test's own environment scrub still cannot be pointed at the
operator's live socket.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import struct
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pytest

__all__ = [
    "HERDR_BINARY",
    "SERVER_READY_TIMEOUT",
    "LiveHerdrServer",
    "OwnedChild",
    "ReadyPoll",
    "ServerReadiness",
    "await_server_ready",
    "create_workspace",
    "herdr_cli",
    "herdr_installed",
    "live_session_names",
    "probe_ready",
    "raw_request",
    "read_frame",
    "require_herdr",
    "session_socket",
    "start_server",
    "stop_server",
    "unique_session",
]

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
READY_METHOD = "ping"
READY_POLL_SECONDS = 0.02
REQUEST_TIMEOUT = 15.0
CLI_TIMEOUT = 60.0
SESSION_PREFIX = "ov-"
LABEL_CHARACTERS = 12
LOG_TAIL_BYTES = 800
# Removed from every server child's environment: it names the OPERATOR's live
# socket on a host that runs herdr, and nothing here has any use for it.
SCRUBBED_VARIABLES = ("HERDR_SOCKET_PATH",)


class OwnedChild(Protocol):
    """The process facts the readiness wait needs from the server it spawned."""

    pid: int

    def poll(self) -> int | None: ...


@dataclass(frozen=True, kw_only=True)
class ReadyPoll:
    """The readiness bound, with an injectable clock for deterministic controls."""

    seconds: float = SERVER_READY_TIMEOUT
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True, kw_only=True)
class ServerReadiness:
    """What proved the server ready: how many probes, whose pid, and its answer."""

    attempts: int
    peer_pid: int
    reply: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class LiveHerdrServer:
    """One owned, request-proven herdr server and where its log went."""

    session: str
    socket_path: str
    server_pid: int
    log_path: Path
    readiness: ServerReadiness


def herdr_installed() -> bool:
    return shutil.which(HERDR_BINARY) is not None


def require_herdr() -> None:
    """Skip the calling exercise when this host has no herdr to drive."""
    if not herdr_installed():
        pytest.skip("herdr is not installed on this host")


def unique_session(*, label: str) -> str:
    """A session name no other call, process or earlier case can share.

    Short on purpose: herdr derives a `herdr-client.sock` path under the session
    directory, and `sun_path` is ~108 bytes.
    """
    safe = "".join(ch if ch.isalnum() else "-" for ch in label)[:LABEL_CHARACTERS].strip("-")
    return f"{SESSION_PREFIX}{safe or 'live'}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def session_socket(*, session: str) -> Path:
    """Where herdr puts `session`'s API socket."""
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def herdr_cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    """One bounded herdr CLI run that can only address a NAMED session.

    Without `--session`, every herdr subcommand except `session ...` addresses the
    operator's default server, so such a call is refused here before it runs.
    """
    assert "--session" in args or args[:1] == [
        "session"
    ], f"refusing a herdr CLI call that would address the default server: {args!r}"
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=CLI_TIMEOUT, check=False
    )


def read_frame(*, conn: socket.socket) -> bytes:
    """Bytes up to and including the first newline, or whatever arrived before EOF."""
    buffered = b""
    while b"\n" not in buffered:
        chunk = conn.recv(65536)
        if not chunk:
            break
        buffered += chunk
    return buffered


def _request_bytes(*, method: str, params: Mapping[str, object]) -> bytes:
    return json.dumps({"id": "fixture", "method": method, "params": dict(params)}).encode() + b"\n"


def raw_request(*, socket_path: str, method: str, params: Mapping[str, object]) -> dict[str, Any]:
    """One raw round trip to a REAL server, for setup and for control facts.

    Control evidence must not come from the surface under test, or an exercise
    would only prove the adapter is self-consistent.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(REQUEST_TIMEOUT)
        sock.connect(socket_path)
        sock.sendall(_request_bytes(method=method, params=params))
        answered = read_frame(conn=sock)
    parsed: dict[str, Any] = json.loads((answered or b"{}").split(b"\n")[0])
    return parsed


def _peer_pid(*, sock: socket.socket) -> int:
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, _uid, _gid = struct.unpack("3i", raw)
    return int(pid)


def probe_ready(*, socket_path: Path, expected_pid: int) -> tuple[str, int, dict[str, Any]]:
    """One readiness attempt: `("", pid, reply)` on success, else `(why_not, pid, {})`.

    The request goes over the SAME connection whose peer credentials were checked,
    so the answer is provably the owned server's and not a stale or rival
    listener's.
    """
    if not socket_path.exists():
        return f"socket path {socket_path} does not exist", 0, {}
    peer = 0
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(REQUEST_TIMEOUT)
        try:
            sock.connect(str(socket_path))
            peer = _peer_pid(sock=sock)
            if peer != expected_pid:
                return (
                    (
                        f"listener at {socket_path} belongs to pid {peer}, "
                        f"not the owned server pid {expected_pid}"
                    ),
                    peer,
                    {},
                )
            sock.sendall(_request_bytes(method=READY_METHOD, params={}))
            answered = read_frame(conn=sock)
        except OSError as failed:
            return f"{type(failed).__name__}: {failed}", 0, {}
    try:
        reply = json.loads(answered.split(b"\n")[0])
    except ValueError:
        return f"{READY_METHOD!r} got no JSON reply: {answered[:200]!r}", peer, {}
    if not isinstance(reply, dict) or "result" not in reply:
        return f"{READY_METHOD!r} was not answered successfully: {str(reply)[:300]}", peer, {}
    return "", peer, reply


def _log_tail(*, log_path: Path) -> str:
    try:
        raw = log_path.read_bytes()
    except OSError as failed:
        return f"<server log unreadable: {failed}>"
    return raw[-LOG_TAIL_BYTES:].decode(errors="replace") or "<server log empty>"


def await_server_ready(
    *, socket_path: Path, session: str, child: OwnedChild, log_path: Path, poll: ReadyPoll
) -> ServerReadiness:
    """Wait until the OWNED child answers a request on `socket_path`, or fail by name."""
    deadline = poll.monotonic() + poll.seconds
    attempts = 0
    reason = "no readiness probe was attempted"
    while True:
        status = child.poll()
        if status is not None:
            raise AssertionError(
                f"herdr session {session!r} owned server process {child.pid} exited with "
                f"status {status} before answering a {READY_METHOD!r} request, after "
                f"{attempts} attempts ({reason}); server log: {_log_tail(log_path=log_path)}"
            )
        if poll.monotonic() >= deadline:
            break
        attempts += 1
        reason, peer, reply = probe_ready(socket_path=socket_path, expected_pid=child.pid)
        if not reason:
            return ServerReadiness(attempts=attempts, peer_pid=peer, reply=reply)
        poll.sleep(READY_POLL_SECONDS)
    raise AssertionError(
        f"herdr session {session!r} never answered a {READY_METHOD!r} request from its owned "
        f"server pid {child.pid} at {socket_path} within {poll.seconds}s after {attempts} "
        f"attempts; the condition that never held: {reason}; "
        f"server log: {_log_tail(log_path=log_path)}"
    )


def _server_environment(*, env: Mapping[str, str] | None, scratch: Path) -> dict[str, str]:
    """The server's environment, minus the operator socket and the operator's shell rc.

    Panes start the login shell, and on the operator host that zsh's ~/.zshrc runs
    atuin and mise hooks around every prompt, so a transient hook child can own the
    pane's foreground exactly when a test reads it. An empty ZDOTDIR keeps every
    pane on a shell that loads no user startup file. The directory holds one EMPTY
    ``.zshrc``: with none at all, zsh runs its interactive new-user wizard instead,
    which swallows the first input a test sends.
    """
    environment = dict(os.environ if env is None else env)
    for name in SCRUBBED_VARIABLES:
        _ = environment.pop(name, None)
    zdotdir = scratch / "zdotdir"
    zdotdir.mkdir(exist_ok=True)
    (zdotdir / ".zshrc").touch()
    environment["ZDOTDIR"] = str(zdotdir)
    return environment


def start_server(
    *,
    scratch: Path,
    label: str = "live",
    session: str | None = None,
    env: Mapping[str, str] | None = None,
    log_name: str | None = None,
    poll: ReadyPoll | None = None,
) -> LiveHerdrServer:
    """Spawn one owned server and return it only once it has ANSWERED a request.

    `session` lets a caller that must know the name before the spawn (to register it
    for cleanup) pass one from :func:`unique_session`; otherwise one is minted from
    `label`. Any failure past the spawn stops and deletes exactly this session.
    """
    require_herdr()
    name = session if session is not None else unique_session(label=label)
    scratch.mkdir(parents=True, exist_ok=True)
    log_path = scratch / (log_name if log_name is not None else f"{name}.log")
    with log_path.open("wb") as log:
        child = subprocess.Popen(  # noqa: S603 — the herdr CLI, not a Python child
            [HERDR_BINARY, "--session", name, "server"],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(scratch),
            env=_server_environment(env=env, scratch=scratch),
        )
    try:
        readiness = await_server_ready(
            socket_path=session_socket(session=name),
            session=name,
            child=child,
            log_path=log_path,
            poll=poll if poll is not None else ReadyPoll(),
        )
    except BaseException:
        stop_server(session=name)
        raise
    return LiveHerdrServer(
        session=name,
        socket_path=str(session_socket(session=name)),
        server_pid=child.pid,
        log_path=log_path,
        readiness=readiness,
    )


def live_session_names() -> set[str]:
    """Names herdr currently reports, through its real CLI."""
    listed = herdr_cli(args=["session", "list", "--json"])
    assert listed.returncode == 0, listed.stderr
    return {str(row["name"]) for row in json.loads(listed.stdout)["sessions"]}


def stop_server(*, session: str) -> None:
    """Stop and delete EXACTLY `session`, then verify it is really gone.

    An absent binary means no session of ours can exist (:func:`start_server`
    requires the binary before it spawns anything), so there is nothing to stop;
    returning is the accurate answer, and it keeps a cleanup `finally` from
    replacing an in-flight skip with a `FileNotFoundError`.
    """
    if not herdr_installed():
        return
    _ = herdr_cli(args=["--session", session, "server", "stop"])
    _ = herdr_cli(args=["session", "delete", session])
    address = session_socket(session=session)
    assert not address.exists(), f"herdr session {session!r} still has a socket at {address}"
    assert session not in live_session_names(), f"herdr session {session!r} is still registered"


def create_workspace(*, socket_path: str, label: str, cwd: str, focus: bool = False) -> str:
    """Create one workspace on the server and return its root pane id."""
    created = raw_request(
        socket_path=socket_path,
        method="workspace.create",
        params={"cwd": cwd, "label": label, "focus": focus},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    return str(created["result"]["root_pane"]["pane_id"])
