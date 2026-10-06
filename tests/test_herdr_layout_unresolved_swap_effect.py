"""Past the swap, an unusable answer is an UNRESOLVED effect — not a clean refusal.

`place_above` reported `effect_unknown=False` for every failure it met after the
swap request had already been answered, which flattened two states a caller must
treat differently into one. The swap is a MUTATION: once its request has crossed
the socket and been answered, the only thing that can settle whether it landed
is an answer the caller can READ. A malformed one settles nothing, and saying
"certainly refused" about a mutation whose fate is unknown invites exactly the
repeat `SPECIFICATION/contracts.md` forbids — a second swap would push the new
pane back BELOW the pane it supervises while every call reported success.

The shapes this file pins, each of which the merged code called certain:

  - a `swap` member that cannot be read as an object at all;
  - a `changed` member that is MISSING, or a string, or any other non-boolean —
    `required_fields` proves `swap` is present, never that its members are
    usable, so these reach the reader;
  - echoed source/target identities naming panes this call did not ask about,
    whether `changed` says true or false. **The echo check has to come FIRST**,
    which is the ordering defect here: `swap_refusal` tested `changed` before the
    identities, so a `changed: false` reply describing FOREIGN panes was trusted
    as proof that nothing moved. It is proof of nothing — it is not about our
    panes;
  - a placement read that is refused outright, or whose layout cannot be parsed,
    or which omits one of the two panes being compared.

The distinction is reported, not merely internal: an unresolved outcome carries
`effect_unknown=True` and still NAMES the created pane, because that pane is
precisely what an operator has to go and re-observe. Nothing is resent.

One case deliberately stays CERTAIN, and it is the control that keeps the rest
honest: a placement read that SUCCEEDS and shows the created pane below the
target is a fully observed state. The rectangles were read; the layout is known;
there is nothing unresolved about it. Unreadability is the trigger, not
disappointment.

These are CONTROLLED socket peers because malformed replies and withheld answers
are invalid-protocol boundaries a healthy server will not produce on demand. The
same two failures are driven against a REAL swap that really took effect in
`tests/test_herdr_live_unresolved_swap_effect.py`.
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
COMMAND = "DO_NOT_SEND_PAST_AN_UNRESOLVED_SWAP"
SHELL_PID = 4100
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


def _layout(*, tops: dict[str, int]) -> dict[str, object]:
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
                for pane_id, top in tops.items()
            ],
        },
    }


def _swap(*, source: str = PANE, target: str = CREATED, **members: object) -> dict[str, object]:
    """A swap reply whose `changed` member is supplied verbatim, or omitted.

    Passing the member through untyped is the whole point: the shapes under test
    are a missing key and values a well-behaved server would never send, so the
    fixture must be able to express them.
    """
    swap: dict[str, object] = {"source_pane_id": source, "target_pane_id": target, **members}
    return {"type": "pane_swap", "swap": swap}


GOOD_GEOMETRY = _layout(tops={CREATED: 0, PANE: 10})
HEALTHY: dict[str, list[dict[str, object]]] = {
    "pane.list": [BEFORE_ROWS, AFTER_ROWS],
    "pane.split": [SPLIT_RESULT],
    "pane.process_info": [IDLE_SHELL],
    "pane.swap": [_swap(changed=True)],
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


def _assert_no_repeat_and_no_launch(*, received: list[bytes], name: str) -> None:
    methods = _methods(received=received)
    assert methods.count("pane.swap") == 1, f"{name}: the swap was repeated: {methods}"
    assert "pane.send_input" not in methods, f"{name}: the command was launched anyway"
    assert not any(
        COMMAND.encode() in raw for raw in received
    ), f"{name}: the command text crossed the socket"


def test_an_unusable_swap_acknowledgement_leaves_the_effect_unresolved(*, socket_dir: Path):
    """Six answers that cannot settle the mutation, all previously called certain.

    Driven as a table because the property is uniformity: an answer about panes
    we did not name and an answer whose `changed` cannot be read are the same
    fact — the server said something, and none of it is about whether OUR swap
    happened.
    """
    cases: dict[str, dict[str, object]] = {
        "the swap member is not an object": {"type": "pane_swap", "swap": "nope"},
        "changed is missing entirely": _swap(),
        "changed is the string 'false'": _swap(changed="false"),
        "changed is a number": _swap(changed=0),
        "a changed reply echoes foreign panes": _swap(changed=True, source="w9:p8", target="w9:p7"),
        "a no-change reply echoes foreign panes": _swap(
            changed=False, source="w9:p8", target="w9:p7", reason="cross_tab"
        ),
    }

    for name, reply in cases.items():
        address = socket_dir / f"{abs(hash(name)) % 100000}.sock"
        received = _serve(address=address, replies=_script(**{"pane.swap": [reply]}))
        outcome = _split_top(address=address)
        assert outcome.ok is False, f"{name}: accepted an unusable acknowledgement"
        assert outcome.pane_id == CREATED, f"{name}: the created pane must still be named"
        assert outcome.effect_unknown is True, f"{name}: reported certain — {outcome.error}"
        _assert_no_repeat_and_no_launch(received=received, name=name)


def test_a_placement_that_cannot_be_observed_leaves_the_effect_unresolved(*, socket_dir: Path):
    """The swap was acknowledged properly; the rectangles are what went missing.

    An unproven placement after a believed swap is the same uncertainty: the
    pane may be above the target or below it, and the honest report is that the
    adapter does not know — never a certain refusal a caller might retry.
    """
    cases: dict[str, dict[str, object]] = {
        "the placement read is refused": OK_RESULT,
        "the layout cannot be parsed": {"type": "pane_layout", "layout": "not an object"},
        "the layout omits the target": _layout(tops={CREATED: 0}),
        "the layout omits the created pane": _layout(tops={PANE: 10}),
    }

    for name, reply in cases.items():
        address = socket_dir / f"{abs(hash(name)) % 100000}.sock"
        received = _serve(address=address, replies=_script(**{"pane.layout": [reply]}))
        outcome = _split_top(address=address)
        assert outcome.ok is False, f"{name}: launched on an unproven placement"
        assert outcome.pane_id == CREATED, f"{name}: the created pane must still be named"
        assert outcome.effect_unknown is True, f"{name}: reported certain — {outcome.error}"
        _assert_no_repeat_and_no_launch(received=received, name=name)


def test_an_observed_wrong_placement_stays_a_certain_known_failure(*, socket_dir: Path):
    """The control: a layout that READS cleanly is known, however unwelcome it is.

    Both rectangles were returned and parsed, so the state is fully observed —
    the created pane is below the target and that is a fact, not an open
    question. Reporting this as unresolved would make the flag mean "the call
    failed" instead of "the mutation's fate is unknown", and the caller would
    lose the one distinction it exists to carry.
    """
    address = socket_dir / "below.sock"
    received = _serve(
        address=address,
        replies=_script(**{"pane.layout": [_layout(tops={PANE: 0, CREATED: 10})]}),
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False, outcome.error
    _assert_no_repeat_and_no_launch(received=received, name="observed below the target")


def test_a_readable_matching_changed_swap_still_proceeds_to_launch(*, socket_dir: Path):
    """The positive control, so none of the above can pass by never working."""
    address = socket_dir / "h.sock"
    received = _serve(address=address, replies=_script())

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False
    assert _methods(received=received).count("pane.send_input") == 1
