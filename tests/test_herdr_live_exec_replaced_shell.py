"""A real shell `exec`-replaced AT THE SAME PID must receive no daemon input.

The retained-shell gate established and rechecked `shell_pid` and its equality
with `foreground_process_group_id`. That pair does not prove a shell, and the
counterexample is not exotic — it is one shell builtin. `exec` REPLACES the
process image in place, so every identifier the gate compared survives it.

Measured on this host against herdr 0.9.3, running `exec sleep 300` in a pane:

    before   shell_pid 179303   group 179303   name bash    /proc exe /usr/bin/bash
    after    shell_pid 179303   group 179303   name sleep   /proc exe /usr/bin/sleep
    /proc starttime 164433575 BOTH BEFORE AND AFTER

Same pid, same process group, same start time — so `shell_pid ==
foreground_process_group_id` still holds and the gate reads an IDLE RETAINED
SHELL. The pane's root is `sleep`. Delivering the daemon command plus Enter
writes it to that program's stdin.

Note what this rules out as a fix: **start time does not discriminate `exec`.**
It is worth carrying anyway, because it discriminates PID REUSE — a different
process arriving at the same number — but anyone reaching for it as the answer
to this defect should see the measurement above first.

**Two orderings, and they fail for different reasons.** A replacement BETWEEN the
two observations is caught by comparing them: same pid, different executable.
A replacement BEFORE either observation cannot be caught that way — both
readings agree, because both describe the impostor — so it needs positive
evidence about what the process IS. Both are driven here.

**The fault injection, stated plainly.** The writer talks to a forwarding
AF_UNIX proxy owned by this test process with a real
`herdr --session <unique> server` behind it; every request and reply is relayed
byte-for-byte and nothing is rewritten. Before the split reply is exposed to the
writer, one disclosed SETUP effect runs: the shared bounded readiness instrument
stages a real self-terminating child, observes it under the created pane's shell,
observes its exit, and establishes that same coherent shell idle again. The
one-shot setup traffic uses its own real-socket connections and is absent from
the writer request stream.

Only after that premise is established does the intended fault run: a REAL
`exec sleep 300` in the created pane over the real socket, at a point chosen per
test. The proxy then polls the REAL `pane.process_info` until the server itself
reports the pane's root is `sleep` at the UNCHANGED pid. The test asserts that
unchanged pid, so "same-PID replacement" is a measurement rather than an
assumption about what `exec` does. If initial readiness expires, the split reply
is withheld and no replacement or writer observation is allowed to stand in for
the missing premise.

The replaced pane's own capture is deliberately NOT used as evidence that
nothing was written: `sleep` does not echo its stdin, so that capture cannot
distinguish delivery from non-delivery. The byte-level statement is that the
adapter issued no `pane.send_input` at all, which the proxy counts; the
original pane's capture is checked because a shell there WOULD echo.
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
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from test_herdr_live_observations import (
    PaneReadiness,
    parent_pid_of,
    registered_login_shells,
    startup_transient,
)

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
REPLACE_TIMEOUT = 20.0
INITIAL_READY_TIMEOUT = 20.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25

# `exec` is the whole point: it replaces the pane's root shell in place rather
# than running a child under it.
REPLACE_COMMAND = "exec sleep 300"
REPLACED_NAME = "sleep"
SHELL_NAME = "bash"
MARKER = "OVEXECREPLACED1"
DAEMON_COMMAND = f"DO_NOT_SEND_TO_A_REPLACED_SHELL_{MARKER}"

# Replace the root BEFORE the adapter has looked at the pane at all: injected
# once the real split reply is in hand, before it reaches the client.
BEFORE_ANY_OBSERVATION = "pane.split"
# Replace the root BETWEEN the adapter's two observations: injected when the
# swap request passes, which is after the pane has been established.
BETWEEN_OBSERVATIONS = "pane.swap"


@dataclass(kw_only=True)
class ProxyState:
    """What the proxy relayed, and the real replacement it injected."""

    inject_at: str
    readiness: PaneReadiness
    created: str = ""
    shell_pid_before: int = 0
    shell_pid_after: int = 0
    replaced: bool = False
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

    session: str
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


def _process_info(*, socket_path: str, pane_id: str) -> dict[str, Any]:
    reply = _raw_request(
        socket_path=socket_path, method="pane.process_info", params={"pane_id": pane_id}
    )
    info: dict[str, Any] = reply["result"]["process_info"]
    return info


def _leader_names(*, info: dict[str, Any]) -> list[str]:
    return [str(entry.get("name")) for entry in info.get("foreground_processes", [])]


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = _raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _live_session_names() -> set[str]:
    """Names Herdr currently reports, through its real CLI."""
    listed = _cli(args=["session", "list", "--json"])
    assert listed.returncode == 0, listed.stderr
    return {str(row["name"]) for row in json.loads(listed.stdout)["sessions"]}


def _geometry(*, socket_path: str, pane_id: str) -> dict[str, int]:
    reply = _raw_request(socket_path=socket_path, method="pane.layout", params={"pane_id": pane_id})
    return {
        str(pane["pane_id"]): int(pane["rect"]["y"]) for pane in reply["result"]["layout"]["panes"]
    }


def _replace_root_shell(*, socket_path: str, state: ProxyState) -> None:
    """`exec` a non-shell over the created pane's root, keeping its pid.

    Waits on the REAL server's own report rather than on a sleep, and records the
    pid on both sides so the test can assert the replacement was in place.
    """
    info = _process_info(socket_path=socket_path, pane_id=state.created)
    state.shell_pid_before = int(info["shell_pid"])
    _ = _raw_request(
        socket_path=socket_path,
        method="pane.send_input",
        params={"pane_id": state.created, "text": REPLACE_COMMAND, "keys": ["Enter"]},
    )
    deadline = time.monotonic() + REPLACE_TIMEOUT
    while time.monotonic() < deadline:
        info = _process_info(socket_path=socket_path, pane_id=state.created)
        if REPLACED_NAME in _leader_names(info=info):
            state.shell_pid_after = int(info["shell_pid"])
            state.replaced = True
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
    """Establish once, relay verbatim, then replace at the chosen point."""
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
            method = str(request["method"])
            if method == state.inject_at and state.created and not state.replaced:
                _replace_root_shell(socket_path=real_socket, state=state)
            answered = _forward(socket_path=real_socket, raw=raw)
            if method == "pane.split" and answered:
                reply = json.loads(answered.split(b"\n")[0])
                state.created = str(reply["result"]["pane"]["pane_id"])
                state.readiness.establish(pane_id=state.created)
                if state.readiness.refusal():
                    continue
                if state.inject_at == BEFORE_ANY_OBSERVATION:
                    _replace_root_shell(socket_path=real_socket, state=state)
            with contextlib.suppress(OSError):
                conn.sendall(answered)


def _start_server(*, session: str, scratch: Path) -> str:
    log = (scratch / f"{session}.log").open("wb")
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
        f"server log: {(scratch / f'{session}.log').read_text(errors='replace')[:500]}"
    )
    return str(address)


def _build(
    *,
    session: str,
    scratch: Path,
    proxy_dir: Path,
    inject_at: str,
    readiness_read: Callable[[], Mapping[str, Any]] | None = None,
    coherence_seconds: float = INITIAL_READY_TIMEOUT,
) -> LiveProxiedTab:
    real_socket = _start_server(session=session, scratch=scratch)
    created = _raw_request(
        socket_path=real_socket,
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    state = ProxyState(
        inject_at=inject_at,
        readiness=PaneReadiness(
            socket_path=real_socket,
            transient=startup_transient(scratch=scratch),
            registered=registered_login_shells(),
            seconds=INITIAL_READY_TIMEOUT,
            coherence_seconds=coherence_seconds,
            read=readiness_read,
        ),
    )
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    proxy_socket = proxy_dir / f"{inject_at.replace('.', '-')}.sock"
    listener.bind(str(proxy_socket))
    listener.listen(16)
    threading.Thread(
        target=_serve_proxy,
        kwargs={"listener": listener, "real_socket": real_socket, "state": state},
        daemon=True,
    ).start()
    return LiveProxiedTab(
        session=session,
        real_socket=real_socket,
        proxy_socket=str(proxy_socket),
        original=str(created["result"]["root_pane"]["pane_id"]),
        state=state,
    )


@pytest.fixture(name="proxied")
def _proxied(*, tmp_path: Path) -> Iterator[Any]:
    """A factory: the two orderings differ only in where the replacement lands."""
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    proxy_dir = Path(os.environ.get("TMPDIR", "/tmp")) / f"hrdrx-{os.getpid()}"
    proxy_dir.mkdir(parents=True, exist_ok=True)
    sessions: list[str] = []

    def build(
        *,
        inject_at: str,
        readiness_read: Callable[[], Mapping[str, Any]] | None = None,
        coherence_seconds: float = INITIAL_READY_TIMEOUT,
    ) -> LiveProxiedTab:
        session = f"overseer-test-{os.getpid()}-{inject_at.replace('.', '-')}"
        sessions.append(session)
        return _build(
            session=session,
            scratch=tmp_path,
            proxy_dir=proxy_dir,
            inject_at=inject_at,
            readiness_read=readiness_read,
            coherence_seconds=coherence_seconds,
        )

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


def _assert_same_pid_replacement_happened(*, live: LiveProxiedTab) -> None:
    """The fixture precondition, asserted rather than assumed.

    If the replacement did not land, or landed at a different pid, this file is
    not testing what it claims and must say so rather than passing.
    """
    state = live.state
    assert state.replaced is True, "the fixture never replaced the pane's root shell"
    assert state.shell_pid_before > 0, state
    assert state.shell_pid_after == state.shell_pid_before, (
        f"the replacement changed the pid ({state.shell_pid_before} -> "
        f"{state.shell_pid_after}), so it is not the same-PID case under test"
    )
    info = _process_info(socket_path=live.real_socket, pane_id=state.created)
    assert REPLACED_NAME in _leader_names(info=info), info
    assert SHELL_NAME not in _leader_names(info=info), info
    assert int(info["foreground_process_group_id"]) == int(info["shell_pid"]), (
        "the replaced root still reports shell_pid == foreground group, which is "
        "exactly why pid equality alone cannot authorize the write"
    )


def _assert_initial_shell_ready(*, live: LiveProxiedTab) -> None:
    """Grade the one-shot native premise before grading the writer's refusal."""
    readiness = live.state.readiness
    assert readiness.panes == [live.state.created], (
        "initial readiness must run exactly once for the created pane; "
        f"created={live.state.created!r}, established={readiness.panes}"
    )
    assert readiness.refusal() == "", readiness.refusal()
    gate = readiness.gate
    assert gate is not None, "a refusal-free readiness must retain its native observations"
    staged = gate.transient
    assert staged is not None and staged.pid is not None, staged
    retained = gate.retained
    assert retained is not None, "the created pane's retained shell identity was not pinned"
    assert parent_pid_of(pid=staged.pid) in (
        None,
        retained.pid,
    ), f"the controlled initial child {staged.pid} was not under shell {retained.pid}"
    assert gate.departed == "", gate.departed
    assert gate.established is not None and gate.established.recovered is True, gate.established
    identity = readiness.identity
    assert identity is not None and identity.coherent is True, readiness.refusal()
    assert (
        identity.shell_pid == retained.pid
    ), f"coherent shell {identity.shell_pid} differs from pinned shell {retained.pid}"
    assert live.state.shell_pid_before == identity.shell_pid, (
        "the replacement must start from the exact shell identity established before "
        f"the writer's first observation: {identity.shell_pid} != "
        f"{live.state.shell_pid_before}"
    )


def _assert_nothing_launched(*, live: LiveProxiedTab, outcome: Any) -> None:
    assert outcome.ok is False, "a pane whose root is not the created shell is not launchable"
    assert outcome.pane_id == live.state.created, "the created pane must still be named"
    assert outcome.effect_unknown is False, outcome.error
    assert live.state.writes() == [], f"input reached {live.state.writes()}"
    assert not any(
        DAEMON_COMMAND.encode() in json.dumps(request).encode() for request in live.state.requests
    ), "the daemon command text crossed the socket"
    assert MARKER not in _capture(
        socket_path=live.real_socket, pane_id=live.original
    ), "the command text reached the supervised pane"


def test_a_root_replaced_before_any_observation_gets_no_input(*, proxied: Any):
    """Both readings describe the impostor, so comparing them cannot help.

    The replacement lands the instant the pane exists, before the adapter has
    looked at it even once. Nothing the two observations have in common is
    wrong — they agree perfectly — so refusing this requires positive evidence
    about what the process at `shell_pid` actually is.
    """
    live = proxied(inject_at=BEFORE_ANY_OBSERVATION)

    outcome = _split_top(live=live)

    _assert_initial_shell_ready(live=live)
    _assert_same_pid_replacement_happened(live=live)
    _assert_nothing_launched(live=live, outcome=outcome)
    tops = _geometry(socket_path=live.real_socket, pane_id=live.original)
    assert live.state.created in tops, f"the partial layout must be preserved: {tops}"


def test_a_root_replaced_between_the_two_observations_gets_no_input(*, proxied: Any):
    """The establish reading saw the real shell; the recheck sees the impostor.

    This is the ordering the recheck exists for, and the one pid equality misses
    most plainly: the pane really was a shell when it was established, and the
    only thing that changed is the program behind the unchanged number.
    """
    live = proxied(inject_at=BETWEEN_OBSERVATIONS)

    outcome = _split_top(live=live)

    _assert_initial_shell_ready(live=live)
    _assert_same_pid_replacement_happened(live=live)
    _assert_nothing_launched(live=live, outcome=outcome)
    assert live.state.methods().count("pane.swap") == 1, live.state.methods()
    info = _process_info(socket_path=live.real_socket, pane_id=live.state.created)
    assert REPLACED_NAME in _leader_names(info=info), "the occupant must not be terminated"


def test_an_expired_initial_shell_premise_is_diagnostic_and_never_injects(*, proxied: Any):
    """Unavailable native identity expires before the split is exposed to the writer.

    The available-shell half still stages and clears its real controlled child.
    Only the independent coherence observation is withheld, through the fixture's
    disclosed read seam. The proxy must therefore close the split round trip with
    a bounded fixture refusal: no first writer observation, swap, replacement, or
    input is allowed to masquerade as evidence about the shipped guard.
    """
    live = proxied(
        inject_at=BETWEEN_OBSERVATIONS,
        readiness_read=lambda: {"result": {}},
        coherence_seconds=0.1,
    )

    outcome = _split_top(live=live)

    refusal = live.state.readiness.refusal()
    assert live.state.readiness.panes == [live.state.created]
    assert live.state.created, "the exact created pane must be named in the fixture refusal"
    assert "never reported a coherent shell identity within 0.1s" in refusal, refusal
    assert "no usable shell/foreground fields" in refusal, refusal
    assert outcome.ok is False, "the withheld split reply cannot produce a successful launch"
    assert live.state.methods() == ["pane.list", "pane.split"], live.state.methods()
    assert live.state.replaced is False, "replacement ran without its initial native premise"
    assert live.state.writes() == [], "the writer sent input after fixture readiness expired"

    _ = _cli(args=["--session", live.session, "server", "stop"])
    _ = _cli(args=["session", "delete", live.session])
    assert not _socket_for(
        session=live.session
    ).exists(), "the expired fixture premise left its exact owned server reachable"
    assert (
        live.session not in _live_session_names()
    ), "the expired fixture premise left its exact owned session registered"
