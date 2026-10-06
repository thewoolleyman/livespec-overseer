"""The layout change addresses the EXACT target pane, and proves the swap landed.

Supplemental regression for two defects found by independent review after
`tests/test_herdr_live_layout.py` was already accepted Green. That file is
unchanged and remains this behaviour's original Red evidence; it passes against
BOTH the defective and the corrected code, and the reason it cannot discriminate
is the whole subject of this file.

**Defect 1 — the split named the wrong parameter, and herdr said nothing.**
`pane.split` takes `target_pane_id`. The adapter sent `pane_id`, which herdr
0.9.3 does not alias and does not reject: unknown members are tolerated
silently, so the call fell through to its default of splitting the FOCUSED pane.
Measured on this host, with `w1:p1` the intended target and `w1:p2` focused:

    before   p1 (0,0,60,40)   p2 (60,0,60,40)
    after    p1 (0,0,60,40)   p2 (60,0,60,10)   new p3 (60,10,60,30)

The supervised pane was untouched and a DIFFERENT pane was split, while the
reply was an ordinary successful `pane_info`. Sending `target_pane_id` instead
splits `w1:p1` correctly and leaves `w1:p2` alone. The accepted live test could
not see any of this because it targeted the root pane, which is focused — so a
focused target masked the bug completely. Every assertion here therefore runs
with the target DELIBERATELY UNFOCUSED and an unrelated pane holding focus.

**Defect 2 — a refused swap was read as a successful one.** `pane.swap` reports
failure INSIDE a successful envelope: a cross-tab swap answers
`{"changed": false, "reason": "cross_tab", ...}` and a same-pane swap answers
`{"changed": false, "reason": "same_pane", ...}`, both with `result` rather than
`error`. The reply type and required members are present, so the expectation
gate passes and the sequence continued to LAUNCH THE COMMAND into a pane that
was never moved above the target. `changed` and the echoed identities are
therefore part of what must be believed, not telemetry.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_sessions
import pytest

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
LAUNCH_COMMAND = "sleep 120"

PANE = "w1:p1"
CREATED = "w1:p2"
SPLIT_RESULT: dict[str, object] = {"type": "pane_info", "pane": {"pane_id": CREATED}}
OK_RESULT: dict[str, object] = {"type": "ok"}
TAB = "w1:t1"


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
SHELL_PID = 4100
# The created pane sitting at its prompt: the shell owns its own foreground
# group. `tests/test_herdr_layout_launch_authorization.py` owns the measured
# shapes and every malformed variant this reading must refuse.
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
HEALTHY: dict[str, list[dict[str, object]]] = {
    "pane.list": [BEFORE_ROWS, AFTER_ROWS],
    "pane.split": [SPLIT_RESULT],
    "pane.process_info": [IDLE_SHELL],
    "pane.layout": [GOOD_GEOMETRY],
    "pane.send_input": [OK_RESULT],
}


def _script(**overrides: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """The healthy script with specific methods replaced."""
    return {**{key: list(value) for key, value in HEALTHY.items()}, **overrides}


def _modules() -> tuple[Any, Any]:
    return (
        importlib.import_module("herdr_write_calls"),
        importlib.import_module("herdr_write"),
    )


def _swap_reply(
    *,
    changed: bool,
    source: str = PANE,
    target: str = CREATED,
    reason: str | None = None,
) -> dict[str, object]:
    swap: dict[str, object] = {
        "changed": changed,
        "source_pane_id": source,
        "target_pane_id": target,
    }
    if reason is not None:
        swap["reason"] = reason
    return {"type": "pane_swap", "swap": swap}


# ---------------------------------------------------------------- live fixture


@dataclass(frozen=True, kw_only=True)
class UnfocusedTab:
    """A live server whose SUPERVISED pane is deliberately not the focused one."""

    socket_path: str
    server_pid: int
    supervised: str
    focused: str


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw socket round trip, used ONLY to set the tab up or read a control fact."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(json.dumps({"id": "fixture", "method": method, "params": params}).encode() + b"\n")
    buffered = b""
    while b"\n" not in buffered:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buffered += chunk
    sock.close()
    parsed: dict[str, Any] = json.loads(buffered.split(b"\n")[0])
    return parsed


def _rects(*, tab: UnfocusedTab) -> tuple[dict[str, tuple[int, int, int, int]], str]:
    """Every pane's FULL rectangle, so a change in the wrong column is visible."""
    reply = _raw_request(
        socket_path=tab.socket_path, method="pane.layout", params={"pane_id": tab.supervised}
    )
    layout = reply["result"]["layout"]
    placed = {
        str(pane["pane_id"]): (
            int(pane["rect"]["x"]),
            int(pane["rect"]["y"]),
            int(pane["rect"]["width"]),
            int(pane["rect"]["height"]),
        )
        for pane in layout["panes"]
    }
    return placed, str(layout["focused_pane_id"])


def _start_unfocused_tab(*, session: str, scratch: Path) -> UnfocusedTab:
    """Build a two-pane tab and move focus AWAY from the pane under supervision."""
    log = (scratch / "server.log").open("wb")
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
    assert address.exists(), f"herdr session {session!r} never created {address}"
    created = _raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    supervised = str(created["result"]["root_pane"]["pane_id"])
    # The sibling is created to the RIGHT, so the two panes occupy separate
    # columns and a split landing in the wrong one is unmistakable.
    sibling = _raw_request(
        socket_path=str(address),
        method="pane.split",
        params={
            "target_pane_id": supervised,
            "direction": "right",
            "ratio": 0.5,
            "cwd": PANE_CWD,
            "focus": False,
        },
    )
    assert "result" in sibling, f"sibling split failed: {sibling}"
    other = str(sibling["result"]["pane"]["pane_id"])
    _ = _raw_request(socket_path=str(address), method="pane.focus", params={"pane_id": other})
    return UnfocusedTab(
        socket_path=str(address),
        server_pid=child.pid,
        supervised=supervised,
        focused=other,
    )


@pytest.fixture(name="tab")
def _tab(*, tmp_path: Path) -> Iterator[UnfocusedTab]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-exact"
    built = _start_unfocused_tab(session=session, scratch=tmp_path)
    try:
        yield built
    finally:
        _ = _cli(args=["--session", session, "server", "stop"])
        _ = _cli(args=["session", "delete", session])


def test_the_split_lands_on_the_supervised_pane_not_the_focused_one(*, tab: UnfocusedTab):
    """THE regression: an unfocused target must still be the pane that is split.

    Asserted on the unrelated pane's FULL rectangle as well as the supervised
    one's, because the defect's signature is precisely that the wrong column
    changes while the right one does not.
    """
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    starttime = claude_sessions.proc_starttime(pid=tab.server_pid)
    assert starttime is not None
    before, focused_before = _rects(tab=tab)
    assert focused_before == tab.focused, "fixture precondition: the target is NOT focused"

    outcome = writer_module.HerdrWriter().split_window_top(
        target=identity.HerdrPaneTarget(
            socket_path=tab.socket_path,
            server_pid=tab.server_pid,
            server_starttime=starttime,
            pane_id=tab.supervised,
        ),
        cwd=PANE_CWD,
        command=LAUNCH_COMMAND,
        ratio=TOP_RATIO,
    )

    assert outcome.ok is True, outcome.error
    after, _focused_after = _rects(tab=tab)
    assert after[tab.focused] == before[tab.focused], (
        f"the FOCUSED unrelated pane was split instead: "
        f"{before[tab.focused]} -> {after[tab.focused]}"
    )
    supervised_x = after[tab.supervised][0]
    new_x, new_y, _width, _height = after[outcome.pane_id]
    assert (
        new_x == supervised_x
    ), f"the new pane landed in column {new_x}, not the supervised pane's {supervised_x}"
    assert new_y < after[tab.supervised][1], "the new pane must sit above the supervised pane"


def test_the_split_parameters_name_the_target_pane_explicitly():
    """`pane_id` is not an alias for `target_pane_id`, and herdr will not say so.

    A pure check, because the wire key is the entire defect and asserting it
    here fails loudly and instantly rather than through a geometry reading.
    """
    calls_module, _writer = _modules()

    params = calls_module.split_down_params(pane_id=PANE, cwd="/tmp", ratio=0.25)

    assert params["target_pane_id"] == PANE, params
    assert "pane_id" not in params, (
        "herdr tolerates unknown members silently, so a stray `pane_id` would be "
        "ignored and the split would fall back to the focused pane"
    )


# -------------------------------------------------- deterministic swap refusals


@pytest.fixture(name="socket_dir")
def _socket_dir() -> Iterator[Path]:
    """A SHORT scratch directory, because an AF_UNIX address is capped near 108 bytes."""
    created = tempfile.mkdtemp(prefix="hrdr")
    yield Path(created)
    shutil.rmtree(created, ignore_errors=True)


def _envelope(*, result: dict[str, object], request_id: str) -> bytes:
    return json.dumps({"id": request_id, "result": result}).encode("utf-8")


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
    request_id: str,
    received: list[bytes],
) -> None:
    """Record the request BEFORE answering it, then answer.

    The order is load-bearing rather than stylistic. `sendall` unblocks the
    client, which returns and runs its assertions immediately; recording
    afterwards races that and intermittently loses the LAST request of a
    sequence, making a correct run look like a missing call.
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
    reply = _next_reply(method=str(json.loads(buffered)["method"]), replies=replies)
    try:
        conn.sendall(_envelope(result=reply, request_id=request_id) + b"\n")
    except OSError:
        return


def _serve_script(
    *, address: Path, replies: dict[str, list[dict[str, object]]], rounds: int = 12
) -> list[bytes]:
    """A controlled peer answering per METHOD, recording every request it reads.

    Dispatch is BY METHOD because `split_window_top` interleaves verification
    reads between its mutations; a positional script would answer `pane.list`
    with a split acknowledgement and prove nothing about the swap handling
    these tests exist to pin.
    """
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(address))
    listener.listen(16)
    received: list[bytes] = []

    def run() -> None:
        listener.settimeout(3.0)
        for index in range(rounds):
            try:
                conn, _ = listener.accept()
            except OSError:
                break
            with conn:
                _answer(
                    conn=conn,
                    replies=replies,
                    request_id=f"rq-{index + 1}",
                    received=received,
                )
        listener.close()

    threading.Thread(target=run, daemon=True).start()
    return received


def _split_top(*, address: Path) -> Any:
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    starttime = claude_sessions.proc_starttime(pid=os.getpid())
    assert starttime is not None
    return writer_module.HerdrWriter(
        request_ids=iter(f"rq-{index}" for index in range(1, 64))
    ).split_window_top(
        target=identity.HerdrPaneTarget(
            socket_path=str(address),
            server_pid=os.getpid(),
            server_starttime=starttime,
            pane_id=PANE,
        ),
        cwd="/tmp",
        command=LAUNCH_COMMAND,
        ratio=0.25,
    )


def _methods(*, received: list[bytes]) -> list[str]:
    return [str(json.loads(raw)["method"]) for raw in received]


def test_a_cross_tab_swap_fails_closed_and_never_launches(*, socket_dir: Path):
    """`changed: false` is a REFUSAL wearing a successful envelope.

    The command must not be launched into a pane that was never moved above the
    target — that would leave a daemon running somewhere nobody is looking while
    the call reported success.
    """
    address = socket_dir / "h.sock"
    received = _serve_script(
        address=address,
        replies=_script(**{"pane.swap": [_swap_reply(changed=False, reason="cross_tab")]}),
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert outcome.pane_id == CREATED, "the created pane must still be named for re-observation"
    assert "cross_tab" in outcome.error or "swap" in outcome.error, outcome.error
    assert _methods(received=received) == [
        "pane.list",
        "pane.split",
        "pane.list",
        "pane.process_info",
        "pane.swap",
    ], "the launch must not follow a swap that did not happen"


def test_a_same_pane_swap_fails_closed_and_never_launches(*, socket_dir: Path):
    """The other measured `changed: false` shape refuses identically."""
    address = socket_dir / "h.sock"
    received = _serve_script(
        address=address,
        replies=_script(**{"pane.swap": [_swap_reply(changed=False, reason="same_pane")]}),
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert _methods(received=received) == [
        "pane.list",
        "pane.split",
        "pane.list",
        "pane.process_info",
        "pane.swap",
    ]


def test_a_swap_echoing_other_panes_fails_closed(*, socket_dir: Path):
    """A swap that reports moving panes we did not name has not done our work.

    `changed: true` alone would accept a reply about an entirely different pair,
    which is the same class of error the observation adapter's pane-echo check
    already refuses on the read side.
    """
    address = socket_dir / "h.sock"
    received = _serve_script(
        address=address,
        replies=_script(
            **{"pane.swap": [_swap_reply(changed=True, source="w9:p8", target="w9:p7")]}
        ),
    )

    outcome = _split_top(address=address)

    assert outcome.ok is False
    assert _methods(received=received) == [
        "pane.list",
        "pane.split",
        "pane.list",
        "pane.process_info",
        "pane.swap",
    ]


def test_a_swap_that_changed_and_echoes_our_panes_proceeds_to_launch(*, socket_dir: Path):
    """The positive control, so the refusals above cannot pass by never working."""
    address = socket_dir / "h.sock"
    received = _serve_script(
        address=address,
        replies=_script(**{"pane.swap": [_swap_reply(changed=True)]}),
    )

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    assert outcome.pane_id == CREATED
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


def test_the_split_request_on_the_wire_carries_the_target_key(*, socket_dir: Path):
    """End to end on the socket: the bytes herdr would receive name the target."""
    address = socket_dir / "h.sock"
    received = _serve_script(
        address=address,
        replies=_script(**{"pane.swap": [_swap_reply(changed=True)]}),
    )

    outcome = _split_top(address=address)

    assert outcome.ok is True, outcome.error
    sent = next(
        json.loads(raw)["params"] for raw in received if json.loads(raw)["method"] == "pane.split"
    )
    assert sent["target_pane_id"] == PANE, sent
    assert "pane_id" not in sent, sent
