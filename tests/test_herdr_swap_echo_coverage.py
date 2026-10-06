"""A swap reply that does not say WHICH panes it moved settles nothing.

**COVERAGE, not Red evidence, and the distinction is the point of this header.**
Every assertion here passed the moment it was first written, against the
echo-ordering fix already landed in `swap_verdict`. Nothing in this file drove a
product change; it exists because an independent review asked for these shapes
to be pinned explicitly, and pinning an already-correct behaviour is coverage. It
would have been dishonest to stage it as a failing regression.

The shapes are the ABSENT-echo family. `swap_verdict` compares the reply's
`source_pane_id` and `target_pane_id` against the panes the call named, and a
MISSING member compares unequal exactly as a foreign one does — so a reply that
omits either is refused, and refused as UNRESOLVED, because the request had
already crossed the socket and an answer that does not identify its subject
cannot say whether this swap happened.

**The contrast with a valid refusal is the whole reason both live in one file.**

| reply | verdict | `effect_unknown` |
|---|---|---|
| `changed: false`, echoes MISSING | refused | `True` — unknown |
| `changed: false`, echoes MATCHING | refused | `False` — known |

Those two differ by nothing except whether the reply says what it is about, and
they must land in different buckets. The second is the server explicitly
declining a swap of OUR panes — a fact about a mutation that did not happen, and
therefore certain. The first is a decline about nothing in particular, which is
not evidence that our panes were left alone. Reading it as one would let a caller
treat an unresolved mutation as safe to reconsider.

That ordering is why `changed` is checked AFTER the identities and not before:
with the old order, `changed: false` short-circuited and every reply in the top
row was reported certain.

`tests/test_herdr_layout_unresolved_swap_effect.py` owns the foreign-echo and
malformed-`changed` families end to end; this file adds the absent-echo family at
the parser, plus one end-to-end case so the verdict is shown reaching a caller
rather than only being computed.
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

# The scripted `shell_pid` names no live process, so the retained-shell proof's
# KERNEL half is injected; see `tests/test_herdr_shell_identity_evidence.py`.
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
COMMAND = "DO_NOT_SEND_ON_AN_ANONYMOUS_SWAP"
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
# A well-formed decline naming NEITHER pane: the end-to-end case below.
ANONYMOUS_DECLINE: dict[str, object] = {
    "type": "pane_swap",
    "swap": {"changed": False, "reason": "cross_tab"},
}
MATCHING_DECLINE: dict[str, object] = {
    "type": "pane_swap",
    "swap": {
        "changed": False,
        "reason": "cross_tab",
        "source_pane_id": PANE,
        "target_pane_id": CREATED,
    },
}

HEALTHY: dict[str, list[dict[str, object]]] = {
    "pane.list": [BEFORE_ROWS, AFTER_ROWS],
    "pane.split": [SPLIT_RESULT],
    "pane.process_info": [IDLE_SHELL],
    "pane.swap": [MATCHING_DECLINE],
    "pane.layout": [GOOD_GEOMETRY],
    "pane.send_input": [OK_RESULT],
}


def _script(**overrides: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
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


def _verdict(*, swap: dict[str, object]) -> Any:
    calls_module = importlib.import_module("herdr_write_calls")
    return calls_module.swap_verdict(
        result={"swap": swap}, source_pane_id=PANE, target_pane_id=CREATED
    )


def test_a_swap_reply_omitting_either_echo_is_refused_as_unresolved():
    """An absent echo compares unequal exactly as a foreign one does, and must.

    Driven across both members and both `changed` values, plus a reply carrying
    neither member nor `changed`, because the property is that identity is
    settled FIRST — whatever else the reply does or does not say.
    """
    cases = {
        "source absent, changed true": {"changed": True, "target_pane_id": CREATED},
        "target absent, changed true": {"changed": True, "source_pane_id": PANE},
        "both absent, changed true": {"changed": True},
        "source absent, changed false": {
            "changed": False,
            "target_pane_id": CREATED,
            "reason": "cross_tab",
        },
        "both absent, changed false": {"changed": False, "reason": "same_pane"},
        "both absent, no changed at all": {},
    }

    for name, swap in cases.items():
        verdict = _verdict(swap=swap)

        assert verdict.error, f"{name}: believed a reply that names no panes"
        assert verdict.effect_unknown is True, f"{name}: reported certain — {verdict.error}"


def test_a_matching_boolean_no_change_is_known_while_an_anonymous_one_is_not():
    """THE distinction the review asked to see confirmed, asserted side by side.

    These two replies differ by nothing but whether they say what they are
    about. Asserting them in one test is deliberate: the risk is not that either
    verdict is wrong in isolation, it is that they collapse into each other.
    """
    matching = _verdict(
        swap={
            "changed": False,
            "reason": "cross_tab",
            "source_pane_id": PANE,
            "target_pane_id": CREATED,
        }
    )
    anonymous = _verdict(swap={"changed": False, "reason": "cross_tab"})

    assert matching.error, "an explicit decline is still a refusal"
    assert (
        matching.effect_unknown is False
    ), f"a valid matching changed=false is KNOWN, not unknown: {matching.error}"
    assert anonymous.effect_unknown is True, "a decline about nothing settles nothing"
    assert (matching.error, matching.effect_unknown) != (
        anonymous.error,
        anonymous.effect_unknown,
    ), "the two must not collapse into one verdict"


def test_an_anonymous_decline_reaches_the_caller_as_an_unresolved_effect(*, socket_dir: Path):
    """The verdict shown arriving at a caller, not merely computed.

    One end-to-end case, because `effect_unknown` only matters if it survives
    the trip into `LayoutOutcome`: the created pane is still named, the flag is
    set, and neither the swap nor the launch is repeated.
    """
    address = socket_dir / "anon.sock"
    received = _serve(address=address, replies=_script(**{"pane.swap": [ANONYMOUS_DECLINE]}))

    outcome = _split_top(address=address)

    methods = [str(json.loads(raw)["method"]) for raw in received]
    assert outcome.ok is False
    assert outcome.pane_id == CREATED, "the created pane must still be named"
    assert outcome.effect_unknown is True, outcome.error
    assert methods.count("pane.swap") == 1, methods
    assert "pane.send_input" not in methods, "the command was delivered"


def test_a_matching_decline_reaches_the_caller_as_a_known_partial_failure(*, socket_dir: Path):
    """The other half of the same trip, so the control is not a different harness."""
    address = socket_dir / "match.sock"
    received = _serve(address=address, replies=_script())

    outcome = _split_top(address=address)

    methods = [str(json.loads(raw)["method"]) for raw in received]
    assert outcome.ok is False
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False, f"a matching decline is known: {outcome.error}"
    assert "cross_tab" in outcome.error, outcome.error
    assert "pane.send_input" not in methods, "the command was delivered"
