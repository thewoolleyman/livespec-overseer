"""A new herdr pane must PROVE it is an idle retained shell before input reaches it.

`split_window_top` went from a verified GEOMETRY straight to `pane.send_input`.
Geometry is the wrong evidence for that step: it proves where the pane is, not
what is running inside it. Between the split that created the pane and the write
that launches the daemon into it there are three further round trips, and a pane
is perfectly capable of acquiring a foreground child across them — a shell
`.bashrc` job, an operator typing into it, or anything else that reaches a live
terminal. Delivering a command plus Enter into that pane submits it to whatever
owns the foreground instead of to the shell.

So the launch now rests on PROCESS evidence, taken twice:

  - **Establish.** Immediately after the created pane is proven new, live and in
    the target's tab, `pane.process_info` for THAT pane on THAT generation must
    report an idle retained shell — `shell_pid` positive and equal to
    `foreground_process_group_id`, which is exactly how herdr 0.9.3 reports a
    pane sitting at its prompt (measured: `shell_pid 22420` against
    `foreground_process_group_id 22420`, the shell itself listed as the group
    leader). That pid becomes the expected shell.
  - **Recheck.** Immediately before the command is written, the same reading is
    taken again and must still name that EXACT shell pid, still idle, still for
    that pane. A different `shell_pid` is a replaced shell; a different group id
    is an occupied one (measured occupied: `shell_pid 22420` against
    `foreground_process_group_id 22447`, leader `sleep`).

**An executable NAME is not shell identity — and neither is a pid. This
paragraph CORRECTS an earlier version of itself, prospectively.** It used to say
that every judgement here is made on pids, which overstated this file's scope and
was wrong as a statement of the product contract. A pid is not identity either:
`exec` replaces a process image in place, keeping the pid, the process group AND
the `/proc` start time, so a foreign program can inherit every number the first
cut of this gate compared. The contract therefore rests on live KERNEL evidence
about the process — which this file INJECTS, because its scripted `shell_pid`
names no live process — with the server's reported name required to AGREE with
that evidence rather than to be believed on its own. The rule is pinned by
`tests/test_herdr_shell_identity_evidence.py` and driven against a really
exec-replaced root in `tests/test_herdr_live_exec_replaced_shell.py`. Nothing
below changed meaning: the positive data here always described `bash`, and the
added evidence checks agree with it.

Any missing, malformed, ambiguous, foreign, replaced or occupied reading stops
the launch. What it must NOT do is tidy up: the created pane is real and
correctly placed, so the outcome keeps naming it and the partial layout is left
exactly as it stands for an operator to re-observe. Nothing is killed, nothing
is closed, and no mutation is repeated.

These are CONTROLLED socket peers rather than a herdr server, because the
readings under test include shapes a healthy server will not emit on demand (an
unreadable payload, a duplicate pid, a foreign pane echo). The equivalent
behaviour against a REAL server — a genuine foreground child occupying the
newly created pane before the launch — is proven in
`tests/test_herdr_live_occupied_pane_launch.py`.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

# The scripted `shell_pid` below names no live process, so the retained-shell
# proof's KERNEL half is injected here. These files stage REPLY shapes; the
# live-evidence rule itself is pinned by
# `tests/test_herdr_shell_identity_evidence.py` and driven against a real
# exec-replaced root in `tests/test_herdr_live_exec_replaced_shell.py`.
SHELL_EXECUTABLE = "/usr/bin/bash"
LOGIN_SHELLS = frozenset({SHELL_EXECUTABLE})
SHELL_STARTTIME = "164433575"


def _shell_evidence(*, pid: int) -> Any:
    """Kernel evidence for any pid: the login shell these fixtures describe."""
    identity = importlib.import_module("_herdr_shell_identity")
    return identity.ShellIdentity(pid=pid, executable=SHELL_EXECUTABLE, starttime=SHELL_STARTTIME)


PANE = "w1:p1"
CREATED = "w1:p2"
TAB = "w1:t1"
COMMAND = "DO_NOT_SEND_TO_AN_UNPROVEN_PANE"
SHELL_PID = 4100
CHILD_PID = 4200


def _row(*, pane_id: str) -> dict[str, object]:
    return {
        "pane_id": pane_id,
        "tab_id": TAB,
        "workspace_id": "w1",
        "cwd": "/tmp",
        "foreground_cwd": "/tmp",
        "focused": pane_id == PANE,
    }


def _process_info(*, pane_id: str, shell_pid: int, group_id: int) -> dict[str, object]:
    """A measured `pane.process_info` reply, idle when the shell owns the group.

    The leader entry's NAME is derived from the relationship so the fixture reads
    like the real thing. An earlier version of this docstring added that nothing
    under test may consult it; that is CORRECTED, prospectively — the name is
    consulted, as one of two sources that must agree, and it was never permitted
    to decide on its own. See this file's header.
    """
    leader = "bash" if group_id == shell_pid else "sleep"
    return {
        "type": "pane_process_info",
        "process_info": {
            "pane_id": pane_id,
            "shell_pid": shell_pid,
            "foreground_process_group_id": group_id,
            "foreground_processes": [
                {"pid": group_id, "name": leader, "cmdline": leader, "cwd": "/tmp"}
            ],
        },
    }


OK_RESULT: dict[str, object] = {"type": "ok"}
SPLIT_RESULT: dict[str, object] = {"type": "pane_info", "pane": {"pane_id": CREATED}}
SWAP_RESULT: dict[str, object] = {
    "type": "pane_swap",
    "swap": {"changed": True, "source_pane_id": PANE, "target_pane_id": CREATED},
}
BEFORE_ROWS: dict[str, object] = {"type": "pane_list", "panes": [_row(pane_id=PANE)]}
AFTER_ROWS: dict[str, object] = {
    "type": "pane_list",
    "panes": [_row(pane_id=PANE), _row(pane_id=CREATED)],
}
GOOD_GEOMETRY: dict[str, object] = {
    "type": "pane_layout",
    "layout": {
        "workspace_id": "w1",
        "tab_id": TAB,
        "zoomed": False,
        "area": {"x": 0, "y": 0, "width": 120, "height": 40},
        "focused_pane_id": PANE,
        "panes": [
            {"pane_id": CREATED, "focused": False, "rect": {"x": 0, "y": 0, "height": 10}},
            {"pane_id": PANE, "focused": True, "rect": {"x": 0, "y": 10, "height": 30}},
        ],
    },
}

IDLE = _process_info(pane_id=CREATED, shell_pid=SHELL_PID, group_id=SHELL_PID)
OCCUPIED = _process_info(pane_id=CREATED, shell_pid=SHELL_PID, group_id=CHILD_PID)
REPLACED = _process_info(pane_id=CREATED, shell_pid=SHELL_PID + 7, group_id=SHELL_PID + 7)
FOREIGN = _process_info(pane_id=PANE, shell_pid=SHELL_PID, group_id=SHELL_PID)
UNREADABLE: dict[str, object] = {"type": "pane_process_info", "process_info": "not an object"}
NO_SHELL = _process_info(pane_id=CREATED, shell_pid=0, group_id=0)
# Two entries both claiming the foreground group: the leader cannot be selected
# by group ownership, so the reading is AMBIGUOUS rather than merely occupied.
AMBIGUOUS: dict[str, object] = {
    "type": "pane_process_info",
    "process_info": {
        "pane_id": CREATED,
        "shell_pid": SHELL_PID,
        "foreground_process_group_id": CHILD_PID,
        "foreground_processes": [
            {"pid": CHILD_PID, "name": "bash", "cmdline": "bash", "cwd": "/tmp"},
            {"pid": CHILD_PID, "name": "sleep", "cmdline": "sleep", "cwd": "/tmp"},
        ],
    },
}

# The verified sequence: enumerate, split, re-enumerate, ESTABLISH the retained
# shell, swap, re-measure, RECHECK the retained shell, launch.
HEALTHY: dict[str, list[dict[str, object]]] = {
    "pane.list": [BEFORE_ROWS, AFTER_ROWS],
    "pane.split": [SPLIT_RESULT],
    "pane.process_info": [IDLE],
    "pane.swap": [SWAP_RESULT],
    "pane.layout": [GOOD_GEOMETRY],
    "pane.send_input": [OK_RESULT],
}


def _script(**overrides: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """The healthy script with specific methods replaced."""
    return {**{key: list(value) for key, value in HEALTHY.items()}, **overrides}


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _next_reply(*, method: str, replies: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    """The next scripted reply for `method`, repeating the last once exhausted."""
    queued = replies.get(method)
    if not queued:
        return OK_RESULT
    return queued.pop(0) if len(queued) > 1 else queued[0]


def _answer(
    *,
    conn: socket.socket,
    replies: dict[str, list[dict[str, object]]],
    received: list[bytes],
) -> None:
    """Record the request BEFORE answering it, then answer whatever its method asks.

    Recording first is load-bearing: `sendall` unblocks the client, which runs
    its assertions immediately, and recording afterwards intermittently loses
    the last request of a sequence.
    """
    conn.settimeout(5.0)
    buffered = b""
    try:
        while not buffered.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                break
            buffered += chunk
    except OSError:
        return
    if not buffered:
        return
    received.append(buffered)
    request = json.loads(buffered)
    reply = _next_reply(method=str(request["method"]), replies=replies)
    try:
        conn.sendall(json.dumps({"id": request["id"], "result": reply}).encode() + b"\n")
    except OSError:
        return


def _serve(
    *, address: Path, replies: dict[str, list[dict[str, object]]], rounds: int = 14
) -> list[bytes]:
    """A real AF_UNIX peer answering per METHOD, recording every request it reads."""
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(16)
    received: list[bytes] = []

    def run() -> None:
        listener.settimeout(3.0)
        for _ in range(rounds):
            try:
                conn, _peer = listener.accept()
            except OSError:
                break
            with conn:
                _answer(conn=conn, replies=replies, received=received)
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _split_top(*, address: Path) -> Any:
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None, "this process must have a readable /proc start time"
    return writer_module.HerdrWriter(
        shell_evidence_of=_shell_evidence, login_shells=LOGIN_SHELLS
    ).split_window_top(
        target=identity.HerdrPaneTarget(
            socket_path=str(address),
            server_pid=os.getpid(),
            server_starttime=starttime,
            pane_id=PANE,
        ),
        cwd="/tmp",
        command=COMMAND,
        ratio=0.25,
    )


def _methods(*, received: list[bytes]) -> list[str]:
    return [str(json.loads(raw)["method"]) for raw in received]


def _writes_to(*, received: list[bytes]) -> list[str]:
    """Every pane the adapter actually sent input to."""
    return [
        str(json.loads(raw)["params"].get("pane_id"))
        for raw in received
        if json.loads(raw)["method"] == "pane.send_input"
    ]


def _assert_nothing_launched(*, received: list[bytes]) -> None:
    assert _writes_to(received=received) == [], f"input reached {_writes_to(received=received)}"
    assert not any(
        COMMAND.encode() in raw for raw in received
    ), "the daemon command text must never cross the socket without process evidence"


def _process_reads(*, received: list[bytes]) -> list[str]:
    """The pane each `pane.process_info` request named, in order."""
    return [
        str(json.loads(raw)["params"].get("pane_id"))
        for raw in received
        if json.loads(raw)["method"] == "pane.process_info"
    ]


def test_a_new_pane_occupied_between_the_split_and_the_launch_gets_no_input(*, socket_dir: Path):
    """THE defect: the pane was idle when created and is BUSY when written to.

    The first reading authorizes nothing by itself — it only establishes which
    shell the command is for. The second is what the write rests on, and here it
    reports a foreground child owning the pane, so the command is withheld.
    """
    address = socket_dir / "h.sock"
    received = _serve(address=address, replies=_script(**{"pane.process_info": [IDLE, OCCUPIED]}))

    outcome = _split_top(address=address)

    assert outcome.ok is False, "an occupied pane may not be launched into"
    assert outcome.pane_id == CREATED, "the created pane must still be named for re-observation"
    assert outcome.effect_unknown is False, outcome.error
    _assert_nothing_launched(received=received)
    assert _methods(received=received).count("pane.swap") == 1, "the swap must not be repeated"


def test_every_untrustworthy_process_reading_stops_the_launch(*, socket_dir: Path):
    """Six ways to be unable to prove an idle retained shell, none of which may write.

    Driven as a table because uniformity is the property: a reading that is
    missing, unparsable, ambiguous about its leader, about a different pane, or
    about a different shell is no more an authorization than one that reports a
    live child. Stating them separately would make an inconsistency easier to
    miss than it already is.
    """
    cases: dict[str, list[dict[str, object]]] = {
        "already occupied when established": [OCCUPIED],
        "the reading is refused outright": [OK_RESULT],
        "the payload is unreadable": [UNREADABLE],
        "there is no usable shell pid": [NO_SHELL],
        "the foreground group leader is ambiguous": [AMBIGUOUS],
        "the reading describes another pane": [FOREIGN],
        "the shell was replaced before the launch": [IDLE, REPLACED],
    }

    for name, readings in cases.items():
        address = socket_dir / f"{abs(hash(name)) % 100000}.sock"
        received = _serve(address=address, replies=_script(**{"pane.process_info": readings}))
        outcome = _split_top(address=address)
        assert outcome.ok is False, f"{name}: launched without process evidence"
        assert outcome.pane_id == CREATED, f"{name}: the partial layout must stay reported"
        _assert_nothing_launched(received=received)


def test_a_verified_idle_retained_shell_is_read_twice_and_then_launched(*, socket_dir: Path):
    """The positive control: both readings name the CREATED pane, and only then input.

    The ESTABLISH read sits between the split and the swap, and the RECHECK read
    immediately before the write, so neither is a stale fact carried across a
    mutation. Both name the created pane rather than the target — writing the
    daemon command after reading the supervised pane's processes would prove
    nothing at all.
    """
    address = socket_dir / "h.sock"
    received = _serve(address=address, replies=_script())

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False
    assert _methods(received=received) == [
        "pane.list",
        "pane.split",
        "pane.list",
        "pane.process_info",
        "pane.swap",
        "pane.layout",
        "pane.process_info",
        "pane.send_input",
    ]
    assert _process_reads(received=received) == [CREATED, CREATED]
    assert _writes_to(received=received) == [CREATED]
