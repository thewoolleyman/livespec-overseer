"""Three partial-failure states a caller must be able to tell apart, and does.

`place_above` can fail in three materially different places, and what the caller
is allowed to do next differs in each. The outcome has to carry that, because the
caller has no other source for it — re-observing a terminal tells you what IS
there, never whether it is safe to repeat a mutation.

| state | `pane_id` | `effect_unknown` |
|---|---|---|
| refused before any mutation | `""` | `False` |
| a valid matching no-change swap | the created pane | `False` |
| an attempted mutation of unknown fate | the created pane | `True` |

Top row: nothing was created, so the whole call may be reconsidered. Middle
row: the pane EXISTS and was not moved, and that layout is known. Bottom row:
the panes may already be exchanged, so nothing may be repeated.

The middle row is the one this file is named for. `pane.swap` reports a refusal
INSIDE a success envelope — measured on herdr 0.9.3 as
`{"changed": false, "reason": "cross_tab"}` and `{"changed": false, "reason":
"same_pane"}` — and when that reply is well-formed AND echoes exactly the two
panes the call named, it is the server EXPLICITLY DECLINING. That is a fact about
a mutation that did not happen, so it is certain. It is a partial failure all the
same: the split before it did land, so the created pane is real, is reported, and
is left alone.

The two neighbouring rows are what give the middle one meaning, which is why all
three are asserted in one place rather than three. A verdict that cannot be
distinguished from "nothing happened" invites discarding a live pane; one that
cannot be distinguished from "unknown" forbids a reconsideration that is
perfectly safe. `tests/test_herdr_layout_unresolved_swap_effect.py` owns the
unresolved shapes in detail, including why a no-change reply naming FOREIGN
panes belongs in the bottom row instead of the middle one.

The native counterpart is `tests/test_herdr_live_no_change_swap_refusal.py`.
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
ABSENT = "w1:p9"
TAB = "w1:t1"
COMMAND = "DO_NOT_SEND_AFTER_A_REFUSED_SWAP"
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
# A listing that does NOT hold the target: the coordinate names a pane this
# generation does not own, which is refused before anything is created.
UNOWNED_ROWS: dict[str, object] = {"type": "pane_list", "panes": [_row(pane_id=ABSENT)]}
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


def _swap(*, changed: bool, reason: str | None = None) -> dict[str, object]:
    """A well-formed swap reply echoing exactly the panes this call names."""
    swap: dict[str, object] = {
        "changed": changed,
        "source_pane_id": PANE,
        "target_pane_id": CREATED,
    }
    if reason is not None:
        swap["reason"] = reason
    return {"type": "pane_swap", "swap": swap}


HEALTHY: dict[str, list[dict[str, object] | None]] = {
    "pane.list": [BEFORE_ROWS, AFTER_ROWS],
    "pane.split": [SPLIT_RESULT],
    "pane.process_info": [IDLE_SHELL],
    "pane.swap": [_swap(changed=True)],
    "pane.layout": [GOOD_GEOMETRY],
    "pane.send_input": [OK_RESULT],
}


def _script(
    **overrides: list[dict[str, object] | None],
) -> dict[str, list[dict[str, object] | None]]:
    """The healthy script with specific methods replaced."""
    return {**{key: list(value) for key, value in HEALTHY.items()}, **overrides}


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _next_reply(
    *, method: str, replies: dict[str, list[dict[str, object] | None]]
) -> dict[str, object] | None:
    queued = replies.get(method)
    if not queued:
        return OK_RESULT
    return queued.pop(0) if len(queued) > 1 else queued[0]


def _answer(
    *,
    conn: socket.socket,
    replies: dict[str, list[dict[str, object] | None]],
    received: list[bytes],
) -> None:
    """Record then answer; a `None` reply models a committed request left unanswered."""
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
    if reply is None:
        return
    try:
        conn.sendall(json.dumps({"id": request["id"], "result": reply}).encode() + b"\n")
    except OSError:
        return


def _serve(
    *, address: Path, replies: dict[str, list[dict[str, object] | None]], rounds: int = 14
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


def _run(*, socket_dir: Path, name: str, **overrides: list[dict[str, object] | None]) -> Any:
    address = socket_dir / f"{abs(hash(name)) % 100000}.sock"
    received = _serve(address=address, replies=_script(**overrides))
    outcome = _split_top(address=address)
    methods = _methods(received=received)
    assert "pane.send_input" not in methods, f"{name}: the command was delivered"
    assert not any(
        COMMAND.encode() in raw for raw in received
    ), f"{name}: the command text crossed the socket"
    assert methods.count("pane.swap") <= 1, f"{name}: the swap was repeated"
    return outcome


def test_a_valid_matching_no_change_swap_is_a_known_partial_failure(*, socket_dir: Path):
    """The server declined, said so legibly about our panes, and the pane survives.

    Both measured reasons are driven, because the discriminator is the shape of
    the reply rather than the particular reason string — a future reason this
    repository has never seen must land here too.
    """
    for reason in ("cross_tab", "same_pane"):
        outcome = _run(
            socket_dir=socket_dir,
            name=f"declined-{reason}",
            **{"pane.swap": [_swap(changed=False, reason=reason)]},
        )

        assert outcome.ok is False, reason
        assert outcome.pane_id == CREATED, f"{reason}: the created pane must be reported"
        assert outcome.effect_unknown is False, f"{reason}: a decline is certain — {outcome.error}"
        assert reason in outcome.error, outcome.error


def test_a_refusal_before_any_mutation_names_no_pane_at_all(*, socket_dir: Path):
    """The top row: the target is not this server's, so nothing was ever created.

    Reporting a created pane here would be worse than unhelpful — there is no
    such pane, and an operator sent to re-observe it would find nothing.
    """
    outcome = _run(socket_dir=socket_dir, name="unowned", **{"pane.list": [UNOWNED_ROWS]})

    assert outcome.ok is False
    assert outcome.pane_id == "", "nothing may be named as created when nothing was split"
    assert outcome.effect_unknown is False, outcome.error


def test_an_attempted_swap_of_unknown_fate_is_not_mistaken_for_a_decline(*, socket_dir: Path):
    """The bottom row: the request crossed the socket and was never answered.

    Scripted as a server that reads the swap and then goes away, which is what a
    real timeout looks like from the client side. It shares the created pane with
    the middle row and must still be distinguishable from it — on this flag, the
    only place the difference is recorded.
    """
    outcome = _run(socket_dir=socket_dir, name="unanswered", **{"pane.swap": [None]})

    assert outcome.ok is False
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is True, outcome.error


def test_the_three_states_are_pairwise_distinguishable(*, socket_dir: Path):
    """Stated directly, because each test above only sees its own row.

    A reader checking them one at a time can miss that two rows collide; this
    asserts the triple itself is a set of three, which is the property a caller
    actually depends on.
    """
    declined = _run(
        socket_dir=socket_dir,
        name="triple-declined",
        **{"pane.swap": [_swap(changed=False, reason="cross_tab")]},
    )
    premutation = _run(
        socket_dir=socket_dir, name="triple-unowned", **{"pane.list": [UNOWNED_ROWS]}
    )
    unresolved = _run(socket_dir=socket_dir, name="triple-unanswered", **{"pane.swap": [None]})

    verdicts = {
        (outcome.ok, outcome.pane_id, outcome.effect_unknown)
        for outcome in (declined, premutation, unresolved)
    }
    assert len(verdicts) == 3, f"two partial-failure states are indistinguishable: {verdicts}"


def test_a_changed_swap_still_reaches_the_launch(*, socket_dir: Path):
    """The positive control: a decline is read from `changed`, not from the gate."""
    address = socket_dir / "ok.sock"
    received = _serve(address=address, replies=_script())

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
    assert outcome.effect_unknown is False
    assert _methods(received=received).count("pane.send_input") == 1
