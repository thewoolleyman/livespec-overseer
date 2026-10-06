"""The daemon command NEVER reaches the original pane, whatever the server says.

Supplemental regression for a defect an independent reviewer reproduced as a
REAL native wrong effect. `tests/test_herdr_live_layout.py` and
`tests/test_herdr_layout_exact_target.py` are both unchanged; neither can see
this, because both assume the server's account of which pane it created is
true.

**The reproduced effect.** After a split, an acknowledgement naming the
ORIGINAL pane as the pane it created made the adapter swap that pane with
itself and then paste a daemon command plus Enter INTO THE SUPERVISED AGENT.
Confirmed against this branch before any fix here: `ok=True`,
`pane_id='w1:p1'`, and `pane.send_input` carrying `DO_NOT_SEND_TO_AGENT` with
`keys: ['Enter']` addressed to `w1:p1`. The echo check added for the previous
review passes in exactly this case, because source and target genuinely are
the pane the caller named — they are simply both the WRONG pane.

**Why trusting the acknowledgement is the root error.** `new_pane_id` proves a
reply names SOME pane; it cannot prove that pane is new, that it is in the
caller's tab, or that it is not the very pane being supervised. Those are
claims about the live terminal, and only the live terminal can answer them.
So before a single byte of the daemon command is sent, this file requires:

  - a created pane that is DISTINCT from the original, and absent from the
    panes that existed before the split;
  - that pane present in the live enumeration, in the SAME tab as the target;
  - a swap that reports `changed: true` and echoes exactly the two panes asked
    for;
  - live geometry showing the created pane actually ABOVE the target.

Any malformed, wrong-target, same-as-original, `changed: false` or cross-tab
answer must leave the original and every unrelated pane unwritten.

The peer here dispatches BY METHOD rather than by position, so the same script
is meaningful whether the adapter makes three requests or six — a positional
script would silently mis-answer the corrected sequence and prove nothing.
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

ORIGINAL = "w1:p1"
SIBLING = "w1:p2"
CREATED = "w1:p3"
TAB = "w1:t1"
OTHER_TAB = "w1:t2"
COMMAND = "DO_NOT_SEND_TO_AGENT"


def _modules() -> tuple[Any, Any]:
    return (
        importlib.import_module("herdr_write_calls"),
        importlib.import_module("herdr_write"),
    )


def _row(*, pane_id: str, tab_id: str = TAB, focused: bool = False) -> dict[str, object]:
    return {
        "pane_id": pane_id,
        "tab_id": tab_id,
        "workspace_id": "w1",
        "cwd": "/tmp",
        "foreground_cwd": "/tmp",
        "focused": focused,
    }


def _pane_list(*, rows: list[dict[str, object]]) -> dict[str, object]:
    return {"type": "pane_list", "panes": rows}


def _layout(*, tops: dict[str, int]) -> dict[str, object]:
    return {
        "type": "pane_layout",
        "layout": {
            "workspace_id": "w1",
            "tab_id": TAB,
            "zoomed": False,
            "area": {"x": 0, "y": 0, "width": 120, "height": 40},
            "focused_pane_id": ORIGINAL,
            "panes": [
                {
                    "pane_id": pane_id,
                    "focused": pane_id == ORIGINAL,
                    "rect": {"x": 0, "y": top, "width": 120, "height": 10},
                }
                for pane_id, top in tops.items()
            ],
            "splits": [],
        },
    }


def _split_ack(*, pane_id: str, tab_id: str = TAB) -> dict[str, object]:
    return {
        "type": "pane_info",
        "pane": {"pane_id": pane_id, "tab_id": tab_id, "workspace_id": "w1"},
    }


def _swap_ack(*, changed: bool, source: str, target: str, reason: str | None = None):
    swap: dict[str, object] = {
        "changed": changed,
        "source_pane_id": source,
        "target_pane_id": target,
    }
    if reason is not None:
        swap["reason"] = reason
    return {"type": "pane_swap", "swap": swap}


OK_ACK: dict[str, object] = {"type": "ok"}
SHELL_PID = 4100


def _idle_shell(*, pane_id: str) -> dict[str, object]:
    """`pane_id` sitting at its prompt: its shell owns its own foreground group.

    Scripted for every case here, including the ones that refuse earlier, so a
    refusal under test stays the refusal being measured rather than becoming an
    unprovable retained shell. The measured shapes and the malformed variants
    this reading must refuse live in
    `tests/test_herdr_layout_launch_authorization.py`.
    """
    return {
        "type": "pane_process_info",
        "process_info": {
            "pane_id": pane_id,
            "shell_pid": SHELL_PID,
            "foreground_process_group_id": SHELL_PID,
            "foreground_processes": [
                {"pid": SHELL_PID, "name": "bash", "cmdline": "/bin/bash", "cwd": "/tmp"}
            ],
        },
    }


IDLE_SHELL = _idle_shell(pane_id=CREATED)
# The healthy world: two panes before the split, the created pane appearing in
# the same tab afterwards, and geometry showing it above the original.
BEFORE_ROWS = [_row(pane_id=ORIGINAL, focused=True), _row(pane_id=SIBLING)]
AFTER_ROWS = [*BEFORE_ROWS, _row(pane_id=CREATED)]
GOOD_GEOMETRY = _layout(tops={CREATED: 0, ORIGINAL: 10, SIBLING: 20})


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _reply_for(*, method: str, replies: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    """The next scripted reply for `method`, repeating the last one once exhausted."""
    queued = replies.get(method)
    if not queued:
        return OK_ACK
    return queued.pop(0) if len(queued) > 1 else queued[0]


def _answer_by_method(
    *,
    conn: socket.socket,
    replies: dict[str, list[dict[str, object]]],
    received: list[bytes],
) -> None:
    """Read one request, record it, and answer whatever its METHOD is scripted for.

    The request is recorded BEFORE the reply unblocks the client, so a request
    is never lost to the race between this thread and the assertions.
    """
    conn.settimeout(3.0)
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
    reply = _reply_for(method=str(request["method"]), replies=replies)
    try:
        conn.sendall(json.dumps({"id": request["id"], "result": reply}).encode() + b"\n")
    except OSError:
        return


def _serve_by_method(
    *, address: Path, replies: dict[str, list[dict[str, object]]], rounds: int = 12
) -> list[bytes]:
    """A controlled peer answering per METHOD, recording every request it reads.

    Dispatching by method rather than by position is what lets one script serve
    both the current and the corrected request sequences, so a regression here
    measures the adapter's DECISIONS rather than its call count.
    """
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
                _answer_by_method(conn=conn, replies=replies, received=received)
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _split_top(*, address: Path) -> Any:
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None
    return writer_module.HerdrWriter().split_window_top(
        target=identity.HerdrPaneTarget(
            socket_path=str(address),
            server_pid=os.getpid(),
            server_starttime=starttime,
            pane_id=ORIGINAL,
        ),
        cwd="/tmp",
        command=COMMAND,
        ratio=0.25,
    )


def _writes_to(*, received: list[bytes]) -> list[str]:
    """Every pane the adapter actually sent input to."""
    written: list[str] = []
    for raw in received:
        request = json.loads(raw)
        if request["method"] == "pane.send_input":
            written.append(str(request["params"].get("pane_id")))
    return written


def _assert_nothing_written(*, received: list[bytes]) -> None:
    assert (
        _writes_to(received=received) == []
    ), f"the daemon command was sent to {_writes_to(received=received)}"
    assert not any(
        COMMAND.encode() in raw for raw in received
    ), "the daemon command text must never cross the socket after a refusal"


def test_an_acknowledgement_naming_the_original_pane_never_writes_to_it(*, socket_dir: Path):
    """THE reproduced defect: a lying split ack must not arm a write to the agent.

    The swap echo check cannot catch this on its own — source and target really
    are the panes the caller named. What is wrong is that both of them are the
    pane under supervision, which no new pane may ever be.
    """
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [_pane_list(rows=BEFORE_ROWS)],
            "pane.split": [_split_ack(pane_id=ORIGINAL)],
            "pane.swap": [_swap_ack(changed=True, source=ORIGINAL, target=ORIGINAL)],
            "pane.layout": [GOOD_GEOMETRY],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False, "a swap of the original with itself is not a layout change"
    assert (
        outcome.pane_id != ORIGINAL
    ), "the original pane must never be reported as the pane that was created"
    _assert_nothing_written(received=received)


def test_an_acknowledgement_naming_a_pre_existing_pane_is_refused(*, socket_dir: Path):
    """A pane that already existed is not a pane this operation created.

    Without the pre-split enumeration the adapter has no way to tell a genuinely
    new pane from a neighbour, and swapping the target with an unrelated live
    pane would move somebody else's session.
    """
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [_pane_list(rows=BEFORE_ROWS)],
            "pane.split": [_split_ack(pane_id=SIBLING)],
            "pane.swap": [_swap_ack(changed=True, source=ORIGINAL, target=SIBLING)],
            "pane.layout": [GOOD_GEOMETRY],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    _assert_nothing_written(received=received)


def test_a_created_pane_in_another_tab_is_refused_before_any_launch(*, socket_dir: Path):
    """The created pane must live in the TARGET's tab, proven by live enumeration.

    A pane in another tab is the reviewer's first finding: the daemon command
    ran somewhere nobody was looking while the original tab stayed unsplit.
    """
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [
                _pane_list(rows=BEFORE_ROWS),
                _pane_list(rows=[*BEFORE_ROWS, _row(pane_id=CREATED, tab_id=OTHER_TAB)]),
            ],
            "pane.split": [_split_ack(pane_id=CREATED, tab_id=OTHER_TAB)],
            "pane.swap": [_swap_ack(changed=True, source=ORIGINAL, target=CREATED)],
            "pane.layout": [GOOD_GEOMETRY],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert OTHER_TAB in outcome.error or "tab" in outcome.error, outcome.error
    _assert_nothing_written(received=received)


def test_a_cross_tab_swap_refusal_prevents_the_launch(*, socket_dir: Path):
    """`changed: false` with a cross-tab reason must stop the sequence dead."""
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [_pane_list(rows=BEFORE_ROWS), _pane_list(rows=AFTER_ROWS)],
            "pane.split": [_split_ack(pane_id=CREATED)],
            "pane.swap": [
                _swap_ack(changed=False, source=ORIGINAL, target=CREATED, reason="cross_tab")
            ],
            "pane.layout": [GOOD_GEOMETRY],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    _assert_nothing_written(received=received)


def test_geometry_is_reproven_before_the_command_is_launched(*, socket_dir: Path):
    """A swap that CLAIMS success but left the pane below the target is refused.

    `changed: true` is the server's account of its own action; the rectangles
    are the terminal's. Launching on the former alone would put the daemon
    beneath the session it supervises while reporting success.
    """
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [_pane_list(rows=BEFORE_ROWS), _pane_list(rows=AFTER_ROWS)],
            "pane.split": [_split_ack(pane_id=CREATED)],
            "pane.swap": [_swap_ack(changed=True, source=ORIGINAL, target=CREATED)],
            # The created pane is still BELOW the original: the swap did not land.
            "pane.layout": [_layout(tops={ORIGINAL: 0, CREATED: 10, SIBLING: 20})],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    _assert_nothing_written(received=received)


def test_a_target_absent_from_the_live_enumeration_is_refused(*, socket_dir: Path):
    """An unowned target is refused BEFORE the split, so nothing is created.

    This is the live ownership evidence the sequence rests on: if the pane the
    caller named is not there, every later claim about it is unverifiable.
    """
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [_pane_list(rows=[_row(pane_id=SIBLING)])],
            "pane.split": [_split_ack(pane_id=CREATED)],
            "pane.swap": [_swap_ack(changed=True, source=ORIGINAL, target=CREATED)],
            "pane.layout": [GOOD_GEOMETRY],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert outcome.pane_id == "", "nothing may be reported as created when nothing was split"
    assert "pane.split" not in [
        json.loads(raw)["method"] for raw in received
    ], "an unowned target must be refused before anything is created"
    _assert_nothing_written(received=received)


def test_a_fully_evidenced_sequence_still_launches_into_the_new_pane(*, socket_dir: Path):
    """The positive control: every proof satisfied, and the command lands correctly."""
    address = socket_dir / "h.sock"
    received = _serve_by_method(
        address=address,
        replies={
            "pane.list": [_pane_list(rows=BEFORE_ROWS), _pane_list(rows=AFTER_ROWS)],
            "pane.split": [_split_ack(pane_id=CREATED)],
            "pane.swap": [_swap_ack(changed=True, source=ORIGINAL, target=CREATED)],
            "pane.layout": [GOOD_GEOMETRY],
            "pane.process_info": [IDLE_SHELL],
        },
    )

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
    assert _writes_to(received=received) == [
        CREATED
    ], "the command belongs in the created pane and nowhere else"
