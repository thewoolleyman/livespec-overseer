"""A layout naming one pane TWICE cannot place it, and must not be read as if it could.

`pane_tops` built its map by assignment in a loop, so a reply listing the same
pane id more than once kept whichever row arrived LAST and silently discarded
the rest. The placement check then compared that survivor against the target as
though it were the pane's position.

**The consequence is decided by row ORDER, which is the part that makes this
worth a regression of its own.** Measured against the merged parser, with the
created pane duplicated at contradictory offsets and the target at row 10:

    [created y=20, created y=0,  target y=10]  ->  created at 0   ->  LAUNCHES
    [created y=0,  created y=20, target y=10]  ->  created at 20  ->  known failure

One reply, two outcomes, and neither of them is honest: the first writes the
daemon command into a pane whose position was never established, and the second
reports a CERTAIN known failure on evidence that cannot support certainty. A
server that contradicts itself about where a pane is has not told the caller
where the pane is.

**The sibling reader already had this right, which is the standard being applied
here.** `herdr_calls.pane_rows` refuses a whole listing that names one pane
coordinate twice, and its docstring gives the reason: a pane id is unique within
a server by construction, so a listing naming one twice is contradictory, and
"does my pane still exist?" cannot be answered from two conflicting records. The
refusal is on the REPEAT itself rather than on whether the two rows disagree,
because a caller cannot know which fields a server might repeat consistently.
Geometry is the same kind of question — "where is my pane?" — and gets the same
answer.

**After an attempted swap, this is UNRESOLVED rather than refused.** The swap
request crossed the socket and was believed, so the panes may well have been
exchanged; what failed is the attempt to confirm it from the rectangles. That is
the "unavailable or unreadable placement observation" case, so the outcome keeps
naming the created pane, reports `effect_unknown=True`, and repeats nothing.

Driven against CONTROLLED socket peers because a healthy herdr server does not
contradict itself about its own layout on demand.
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
# proof's KERNEL half is injected here; see
# `tests/test_herdr_shell_identity_evidence.py` for the evidence rule itself.
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
COMMAND = "DO_NOT_SEND_ON_A_CONTRADICTORY_LAYOUT"
SHELL_PID = 4100
TARGET_TOP = 10
OK_RESULT: dict[str, object] = {"type": "ok"}
SPLIT_RESULT: dict[str, object] = {"type": "pane_info", "pane": {"pane_id": CREATED}}


def _row(*, pane_id: str) -> dict[str, object]:
    return {
        "pane_id": pane_id,
        "tab_id": TAB,
        "workspace_id": "w1",
        "cwd": "/tmp",
        "foreground_cwd": "/tmp",
        "focused": pane_id == PANE,
    }


BEFORE_ROWS: dict[str, object] = {"type": "pane_list", "panes": [_row(pane_id=PANE)]}
AFTER_ROWS: dict[str, object] = {
    "type": "pane_list",
    "panes": [_row(pane_id=PANE), _row(pane_id=CREATED)],
}
IDLE_SHELL: dict[str, object] = {
    "type": "pane_process_info",
    "process_info": {
        "pane_id": CREATED,
        "shell_pid": SHELL_PID,
        "foreground_process_group_id": SHELL_PID,
        "foreground_processes": [
            {"pid": SHELL_PID, "name": "bash", "cmdline": "/bin/bash", "cwd": "/tmp"}
        ],
    },
}
SWAP_RESULT: dict[str, object] = {
    "type": "pane_swap",
    "swap": {"changed": True, "source_pane_id": PANE, "target_pane_id": CREATED},
}


def _layout(*, rows: list[tuple[str, int]]) -> dict[str, object]:
    """A `pane.layout` reply built from (pane_id, top) pairs, duplicates included.

    Takes a LIST of pairs rather than a mapping precisely so a pane can appear
    twice; a dict fixture could not express the reply under test.
    """
    return {
        "type": "pane_layout",
        "layout": {
            "workspace_id": "w1",
            "tab_id": TAB,
            "zoomed": False,
            "area": {"x": 0, "y": 0, "width": 120, "height": 40},
            "focused_pane_id": PANE,
            "panes": [
                {
                    "pane_id": pane_id,
                    "focused": pane_id == PANE,
                    "rect": {"x": 0, "y": top, "width": 120, "height": 10},
                }
                for pane_id, top in rows
            ],
        },
    }


# The two orders that made one contradictory reply mean two different things.
# `ABOVE_LAST` ends with the created pane above the target, so the surviving row
# satisfied the placement check and the command was launched; `BELOW_LAST` ends
# below it, so the same reply read as a certain known failure.
ABOVE_LAST = _layout(rows=[(CREATED, 20), (CREATED, 0), (PANE, TARGET_TOP)])
BELOW_LAST = _layout(rows=[(CREATED, 0), (CREATED, 20), (PANE, TARGET_TOP)])
# A duplicate whose rows AGREE is refused on the repeat itself, exactly as
# `pane_rows` refuses a repeated listing coordinate.
AGREEING_DUPLICATE = _layout(rows=[(CREATED, 0), (CREATED, 0), (PANE, TARGET_TOP)])
# The target duplicated instead of the created pane: the same ambiguity about the
# other half of the comparison.
TARGET_DUPLICATED = _layout(rows=[(CREATED, 0), (PANE, TARGET_TOP), (PANE, 30)])
GOOD_GEOMETRY = _layout(rows=[(CREATED, 0), (PANE, TARGET_TOP)])

HEALTHY: dict[str, list[dict[str, object]]] = {
    "pane.list": [BEFORE_ROWS, AFTER_ROWS],
    "pane.split": [SPLIT_RESULT],
    "pane.process_info": [IDLE_SHELL],
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
    """Record the request BEFORE answering, so the last one is never lost to the race."""
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


def test_a_contradictory_duplicate_layout_is_unresolved_in_either_row_order(*, socket_dir: Path):
    """THE defect: one reply, two outcomes, chosen by which duplicate row came last.

    Both orders are driven in one test because the property under test is that
    they AGREE. Asserting them separately would let a fix that merely swapped
    which order wins pass half of this file.
    """
    outcomes: list[tuple[bool, str, bool]] = []
    for name, reply in (("above-last", ABOVE_LAST), ("below-last", BELOW_LAST)):
        address = socket_dir / f"{name}.sock"
        received = _serve(address=address, replies=_script(**{"pane.layout": [reply]}))
        outcome = _split_top(address=address)
        methods = _methods(received=received)

        assert outcome.ok is False, f"{name}: launched on a layout that names one pane twice"
        assert outcome.pane_id == CREATED, f"{name}: the created pane must still be named"
        assert outcome.effect_unknown is True, (
            f"{name}: a contradictory placement cannot settle an attempted swap — "
            f"{outcome.error}"
        )
        assert "pane.send_input" not in methods, f"{name}: the command was delivered"
        assert methods.count("pane.swap") == 1, f"{name}: the swap was repeated"
        assert not any(
            COMMAND.encode() in raw for raw in received
        ), f"{name}: the command text crossed the socket"
        outcomes.append((outcome.ok, outcome.pane_id, outcome.effect_unknown))

    assert outcomes[0] == outcomes[1], (
        "the same contradictory reply must mean the same thing in both row orders, "
        f"got {outcomes}"
    )


def test_a_duplicate_pane_row_is_refused_even_when_the_rows_agree(*, socket_dir: Path):
    """The refusal is on the REPEAT, not on the disagreement — as for `pane_rows`.

    A caller cannot know which fields a server might repeat consistently, so a
    reply that agrees with itself today is not evidence that the next one will.
    Both halves of the comparison are driven: the created pane duplicated, and
    the target duplicated.
    """
    for name, reply in (
        ("agreeing-duplicate", AGREEING_DUPLICATE),
        ("target-duplicated", TARGET_DUPLICATED),
    ):
        address = socket_dir / f"{name}.sock"
        received = _serve(address=address, replies=_script(**{"pane.layout": [reply]}))
        outcome = _split_top(address=address)

        assert outcome.ok is False, f"{name}: accepted a layout naming one pane twice"
        assert outcome.pane_id == CREATED, f"{name}: the created pane must still be named"
        assert outcome.effect_unknown is True, f"{name}: reported certain — {outcome.error}"
        assert "pane.send_input" not in _methods(received=received), f"{name}: delivered anyway"


def test_pane_tops_refuses_a_repeated_pane_coordinate_outright():
    """The parser itself, so the rule is pinned where it lives rather than only end to end.

    A partial or last-row-wins map is worse than no map: the placement check
    compares two specific panes, and a map that silently dropped a conflicting
    row is indistinguishable from one taken off an unambiguous reply.
    """
    calls_module = importlib.import_module("herdr_write_calls")

    def tops(*, reply: dict[str, object]) -> Any:
        layout = reply["layout"]
        assert isinstance(layout, dict)
        return calls_module.pane_tops(result={"layout": layout})

    assert tops(reply=GOOD_GEOMETRY) == {CREATED: 0, PANE: TARGET_TOP}
    assert tops(reply=ABOVE_LAST) is None, "a contradictory duplicate yields no geometry"
    assert tops(reply=BELOW_LAST) is None, "and the reverse order yields none either"
    assert tops(reply=AGREEING_DUPLICATE) is None, "a repeat is refused even when it agrees"
    assert tops(reply=TARGET_DUPLICATED) is None, "either pane repeating is enough"


def test_an_unambiguous_layout_still_reaches_the_launch(*, socket_dir: Path):
    """The positive control, so none of the above can pass by never placing anything."""
    address = socket_dir / "good.sock"
    received = _serve(address=address, replies=_script())

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False
    assert _methods(received=received).count("pane.send_input") == 1
