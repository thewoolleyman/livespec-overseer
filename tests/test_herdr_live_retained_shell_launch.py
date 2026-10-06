"""The verified shell runs the command ONCE, and nothing else on any server is written.

The positive half of the retained-shell gate, against real herdr servers. The
refusals are covered by `tests/test_herdr_layout_launch_authorization.py` and
`tests/test_herdr_live_occupied_pane_launch.py`; a gate that refuses everything
would satisfy both of those, so this file pins what must still HAPPEN, and how
narrowly.

What "exactly once as its child" means here, and why each half is asserted from
a different instrument:

  - **As its child** is read from `/proc`: the launched process's parent must be
    the very `shell_pid` the pre-launch reading verified. A command that had
    replaced the pane's shell (an `exec` launch) would show no such parent, and
    a pane whose process exits is CLOSED by herdr — so the retained shell is the
    difference between a reusable daemon pane and one that vanishes.
  - **Exactly once** is NOT read from the pane's capture, and an earlier version
    of this list said it was. A duplicate delivery really would be queued behind
    the running command where process evidence cannot see it — but a capture
    cannot see it either, because a capture counts RENDERED occurrences: one
    delivery renders the command line twice here, as the raw echo and then on
    the prompt line. The byte-level claim is measured where the adapter's own
    request stream is observable, which this unproxied file cannot do; see the
    corrected docstring on the first test for where it lives.

**The blast radius is asserted across TWO live servers, not one.** Herdr pane ids
are unique only within a server — a fresh server's root pane is `w1:p1` every
time — so the id this operation writes to names a different pane on every other
instance. The second server here is pre-built to hold panes with the SAME ids
as the first, including the one that gets the command, so an adapter that
addressed panes by bare id would write into it visibly rather than merely
comparing unequal somewhere. `tests/test_herdr_live_two_servers.py` proves this
for the OBSERVATION surface; the layout write path had no equivalent.

Session isolation is herdr's own `--session` mechanism: every session name
carries this test process's pid, and teardown stops and deletes BY THAT EXACT
NAME, so no other session — including the operator's `default` — is touched.
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

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
# A LIVENESS FLOOR, not a latency budget — and it is deliberately generous.
# The coverage lane runs the whole suite under `pytest -n`, so a freshly spawned
# pane shell competes with every other worker for CPU before it can read its
# input and fork. One run of this file's clean control exceeded a 20s bound that
# passes comfortably in isolation and under a herdr-only parallel run; the bytes
# a real server acknowledged were never in doubt, only how long the child took to
# appear. Exceeding this still fails rather than skipping.
LAUNCH_TIMEOUT = 120.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25

# A trailing `#` comment keeps the marker in the command line the shell echoes
# while leaving an ordinary long-lived `sleep` as the process.
MARKER = "OVLAUNCH1"
LAUNCH_COMMAND = f"sleep 120 #{MARKER}"
LAUNCH_NAME = "sleep"
# Short enough to exit on its own inside the test, which is the "ordinary child
# exit" the pane has to survive.
BRIEF_COMMAND = f"sleep 1 #{MARKER}"
# The decoy server is given enough panes that whatever id the operation creates
# on the real target already exists over there too.
DECOY_PANES = 4


@dataclass(frozen=True, kw_only=True)
class LiveServer:
    """One live herdr server child, its socket and its root pane."""

    session: str
    socket_path: str
    server_pid: int
    root: str


@dataclass(frozen=True, kw_only=True)
class ServerPair:
    """The TARGET server, an unrelated sibling pane on it, and a decoy server."""

    target: LiveServer
    unrelated: str
    decoy: LiveServer


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw round trip, used ONLY for setup and for control facts.

    Control evidence must not come from the surface under test, or the file
    would only prove the adapter is self-consistent.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(json.dumps({"id": "fixture", "method": method, "params": params}).encode() + b"\n")
    buffered = b""
    try:
        while not buffered.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buffered += chunk
    finally:
        sock.close()
    parsed: dict[str, Any] = json.loads((buffered or b"{}").split(b"\n")[0])
    return parsed


def _process_info(*, socket_path: str, pane_id: str) -> dict[str, Any]:
    reply = _raw_request(
        socket_path=socket_path, method="pane.process_info", params={"pane_id": pane_id}
    )
    info: dict[str, Any] = reply["result"]["process_info"]
    return info


def _is_idle(*, info: dict[str, Any]) -> bool:
    return int(info["foreground_process_group_id"]) == int(info["shell_pid"])


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = _raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _pane_ids(*, socket_path: str) -> list[str]:
    reply = _raw_request(socket_path=socket_path, method="pane.list", params={})
    return [str(pane["pane_id"]) for pane in reply["result"]["panes"]]


def _parent_pid_of(*, pid: int) -> int:
    """`pid`'s parent, read from `/proc` — the one place the lineage is a FACT.

    The comm field can contain spaces and parentheses, so the fields after it
    are taken from the LAST close parenthesis rather than by splitting the whole
    line.
    """
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    return int(stat[stat.rindex(")") + 1 :].split()[1])


def _await_foreground(*, socket_path: str, pane_id: str, name: str) -> dict[str, Any]:
    """Poll until `name` is `pane_id`'s foreground process, or the bound expires."""
    deadline = time.monotonic() + LAUNCH_TIMEOUT
    info = _process_info(socket_path=socket_path, pane_id=pane_id)
    while time.monotonic() < deadline:
        info = _process_info(socket_path=socket_path, pane_id=pane_id)
        if any(str(entry.get("name")) == name for entry in info.get("foreground_processes", [])):
            return info
        time.sleep(0.1)
    return info


def _start_server(*, session: str, scratch: Path, log_name: str) -> LiveServer:
    log = (scratch / log_name).open("wb")
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
        f"server log: {(scratch / log_name).read_text(errors='replace')[:500]}"
    )
    created = _raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    return LiveServer(
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        root=str(created["result"]["root_pane"]["pane_id"]),
    )


def _split(*, server: LiveServer, pane_id: str, direction: str) -> str:
    reply = _raw_request(
        socket_path=server.socket_path,
        method="pane.split",
        params={
            "target_pane_id": pane_id,
            "direction": direction,
            "ratio": 0.5,
            "cwd": PANE_CWD,
            "focus": False,
        },
    )
    assert "result" in reply, f"setup split failed: {reply}"
    return str(reply["result"]["pane"]["pane_id"])


@pytest.fixture(name="pair")
def _pair(*, tmp_path: Path) -> Iterator[ServerPair]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    sessions = (
        f"overseer-test-{os.getpid()}-launch-target",
        f"overseer-test-{os.getpid()}-launch-decoy",
    )
    target = _start_server(session=sessions[0], scratch=tmp_path, log_name="target.log")
    unrelated = _split(server=target, pane_id=target.root, direction="right")
    decoy = _start_server(session=sessions[1], scratch=tmp_path, log_name="decoy.log")
    latest = decoy.root
    for _ in range(DECOY_PANES - 1):
        latest = _split(server=decoy, pane_id=latest, direction="right")
    try:
        yield ServerPair(target=target, unrelated=unrelated, decoy=decoy)
    finally:
        for session in sessions:
            _ = _cli(args=["--session", session, "server", "stop"])
            _ = _cli(args=["session", "delete", session])


def _split_top(*, pair: ServerPair, command: str) -> Any:
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=pair.target.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    return writer_module.HerdrWriter().split_window_top(
        target=identity.HerdrPaneTarget(
            socket_path=pair.target.socket_path,
            server_pid=pair.target.server_pid,
            server_starttime=starttime,
            pane_id=pair.target.root,
        ),
        cwd=PANE_CWD,
        command=command,
        ratio=TOP_RATIO,
    )


def test_the_command_runs_once_as_a_child_of_the_verified_retained_shell(*, pair: ServerPair):
    """The launched process is the SHELL'S child, and the command reached this pane.

    Parentage is what distinguishes a retained shell from a replaced one, and it
    is the shell the pre-launch reading verified that must be the parent — not
    merely some shell in some pane.

    **The once-ness assertion here was WRONG and is corrected, prospectively.**
    This test used to assert `capture.count(MARKER) == 1`, and the file header
    argued the capture was the right instrument because a duplicate delivery
    would be queued behind the running command where process evidence could not
    see it. The argument was sound; the instrument was not. Measured on this
    host, ONE delivery renders the command line TWICE — the raw echo of the
    input, then the prompt line carrying it:

        'sleep 120 #OVLAUNCH1\\nroot@host:/tmp# sleep 120 #OVLAUNCH1\\n'

    That is stable, not a race, so the old assertion was passing by luck
    whenever the capture was taken before the prompt line was drawn. A capture
    counts RENDERED occurrences, never deliveries. So this asserts what the
    capture can support — the command reached THIS pane — plus exactly one live
    `sleep` child. The byte-level once-ness is measured where the request stream
    is observable: `tests/test_herdr_live_no_change_swap_refusal.py` asserts the
    adapter's writes are exactly `[created]`, and the deterministic files assert
    `pane.send_input` appears exactly once.
    """
    outcome = _split_top(pair=pair, command=LAUNCH_COMMAND)

    assert outcome.ok is True, outcome.error
    info = _await_foreground(
        socket_path=pair.target.socket_path, pane_id=outcome.pane_id, name=LAUNCH_NAME
    )
    shell_pid = int(info["shell_pid"])
    group_id = int(info["foreground_process_group_id"])
    assert shell_pid > 0, info
    assert group_id != shell_pid, "the command must run UNDER the shell, not replace it"
    launched = [
        int(entry["pid"])
        for entry in info["foreground_processes"]
        if str(entry.get("name")) == LAUNCH_NAME
    ]
    assert len(launched) == 1, info
    assert _parent_pid_of(pid=launched[0]) == shell_pid, (
        f"the launched process {launched[0]} is not a child of the verified "
        f"retained shell {shell_pid}"
    )
    text = _capture(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)
    assert MARKER in text, f"the command never reached {outcome.pane_id}: {text!r}"


def test_the_retained_shell_outlives_an_ordinary_child_exit(*, pair: ServerPair):
    """When the command finishes normally the pane must still be there, and reusable.

    A pane whose process exits is closed by herdr, so an `exec`-style launch
    would take the daemon pane down with its first command. The shell must be
    the same shell afterwards and back to owning its own foreground.
    """
    outcome = _split_top(pair=pair, command=BRIEF_COMMAND)

    assert outcome.ok is True, outcome.error
    before = int(
        _process_info(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)["shell_pid"]
    )
    deadline = time.monotonic() + LAUNCH_TIMEOUT
    info = _process_info(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)
    while time.monotonic() < deadline and not _is_idle(info=info):
        time.sleep(0.1)
        info = _process_info(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)

    assert _is_idle(info=info), f"the child never exited cleanly: {info}"
    assert outcome.pane_id in _pane_ids(
        socket_path=pair.target.socket_path
    ), "the pane must survive its command finishing"
    assert int(info["shell_pid"]) == before, "the retained shell must be the SAME shell"


def test_no_other_pane_on_either_server_receives_the_launch(*, pair: ServerPair):
    """The supervised pane, the bystander, and another server's same-ID panes.

    The decoy server deliberately holds a pane with the id the command was
    written to, so "it went to the right pane" is a claim about instance
    routing and not just about a string.
    """
    outcome = _split_top(pair=pair, command=LAUNCH_COMMAND)

    assert outcome.ok is True, outcome.error
    decoy_panes = _pane_ids(socket_path=pair.decoy.socket_path)
    assert outcome.pane_id in decoy_panes, (
        f"fixture precondition: the decoy server must also hold {outcome.pane_id!r}; "
        f"it holds {decoy_panes}"
    )
    assert pair.target.root in decoy_panes, "fixture precondition: and the target's own id"
    untouched = [
        (pair.target.socket_path, pair.target.root),
        (pair.target.socket_path, pair.unrelated),
        *((pair.decoy.socket_path, pane_id) for pane_id in decoy_panes),
    ]
    for socket_path, pane_id in untouched:
        info = _process_info(socket_path=socket_path, pane_id=pane_id)
        assert _is_idle(info=info), f"{pane_id} was given something to run: {info}"
        assert MARKER not in _capture(
            socket_path=socket_path, pane_id=pane_id
        ), f"the command text reached {pane_id}"
