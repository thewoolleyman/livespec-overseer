"""The native herdr LAYOUT adapter placing a daemon pane above a real live pane.

This is the herdr equivalent of `tmuxio.split_window_top`, which the two-pane
bootstrap uses to run `overseerd` in a TOP pane beside the agent session that
invoked `/overseer` while focus stays on the BOTTOM pane. Every clause of that
sentence is load-bearing, and each is asserted here against a real server:
the daemon goes ABOVE, the original pane keeps its IDENTITY (the agent session
living in it must survive untouched), the original pane keeps FOCUS, and
anything else already on the tab is left alone.

**Driven against a real `herdr --session <unique> server` child process, and
asserted on the SERVER'S OWN layout and process readings** rather than on the
adapter's account of what it did. The control reads below go over a raw socket
deliberately: evidence about the terminal must not come from the surface under
test, or the test would only prove the adapter is self-consistent.

The measurements this file is built from, taken on this host against herdr 0.9.3
/ protocol 22:

  - Herdr supports only `right` and `down` splits, so "above" is necessarily
    `pane.split` with `direction: down` FOLLOWED BY `pane.swap`. Measured on a
    40-row area with `ratio: 0.25`: the original kept `y=0 height=10` and the
    new pane took `y=10 height=30`; after the swap the NEW pane held
    `y=0 height=10` and the original `y=10 height=30`, with both pane ids and
    both shell pids unchanged and `focused_pane_id` still the original.
  - `ratio` is the ORIGINAL pane's share of the split, so the percentage the
    caller asks for is the share the NEW top pane ends up with after the swap.
  - Launching the command with `pane.send_input` text+Enter leaves the pane's
    own shell RUNNING and the command as its foreground process: measured
    `shell_pid 20920` against `foreground_process_group_id 20932` reporting
    `sleep`. An `exec` launch would discard that shell, and a pane whose process
    exits is closed — which is why the retained shell is asserted rather than
    assumed.

**Every launch here runs under a CONTROLLED ready-shell condition, which is a
repair to this file rather than a convenience.** The pane the command goes into
is created by the ADAPTER and read three round trips later, so what sits in its
foreground at that instant is not something fixture setup beforehand can
influence. On the operator host a freshly created pane's `zsh` forks `mise` and
`atuin` while starting up, the adapter's pre-launch reading finds the pane
OCCUPIED, and it refuses the launch — correctly, and the sibling
`tests/test_herdr_layout_exact_target.py` recorded exactly that refusal as a
failure (`w1:p3` occupied by foreground 3618638 rather than the retained shell
3618552). Every `outcome.ok is True` below therefore depended on the host's
login shell being one that loads nothing. `_split_top` now runs the real
sequence through `ReadyShellGate`, which stages a real transient startup child,
OBSERVES it, and then waits for the pane to report an idle retained shell before
the adapter takes its own reading; a gate that cannot establish that condition
fails the exercise by name rather than being reported as the adapter declining.

These tests PASSED before that change and pass after it — on a host whose login
shell loads nothing they are PRESERVATION CONTROLS over guards that already
hold, and none of this is a reproduced host failure or a product Red. What the
staged transient buys is a bounded DISCRIMINATING instance: the premise is now
established rather than inherited from the shell the exercise happens to run
under. `tests/test_herdr_live_observations.py` carries that framing in full.

**Session isolation is herdr's own `--session` mechanism**: every session name
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
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    BoundedPoll,
    ForegroundReading,
    ReadyShellGate,
    await_occupying_child,
    parent_pid_of,
    process_info_reply,
    read_foreground,
    startup_transient,
)

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
WRITE_CALLS_PATH = PACKAGE_DIR / "herdr_write_calls.py"
WRITER_PATH = PACKAGE_DIR / "herdr_write.py"

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
LAUNCH_TIMEOUT = 15.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25

# A long-lived, inert foreground process, so the reading is stable while the
# assertions run and nothing is left behind after teardown.
LAUNCH_COMMAND = "sleep 120"
LAUNCH_NAME = "sleep"


@dataclass(frozen=True, kw_only=True)
class LiveTab:
    """A live herdr server with an original pane and one UNRELATED sibling pane."""

    socket_path: str
    server_pid: int
    original: str
    unrelated: str
    transient: str


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


def _geometry(*, live: LiveTab) -> tuple[dict[str, tuple[int, int]], str]:
    """Every pane's `(top, height)` on the tab, plus the focused pane id."""
    reply = _raw_request(
        socket_path=live.socket_path, method="pane.layout", params={"pane_id": live.original}
    )
    layout = reply["result"]["layout"]
    placed = {
        str(pane["pane_id"]): (int(pane["rect"]["y"]), int(pane["rect"]["height"]))
        for pane in layout["panes"]
    }
    return placed, str(layout["focused_pane_id"])


def _reading(*, live: LiveTab, pane_id: str) -> ForegroundReading:
    """`pane_id`'s live process reading, or an explicit FIXTURE failure.

    An unusable reply is a failed control read rather than a fact about the
    pane, so it stops here instead of raising out of whichever assertion first
    touched a field the server never sent.
    """
    reading = read_foreground(
        reply=process_info_reply(socket_path=live.socket_path, pane_id=pane_id)
    )
    assert reading is not None, f"herdr returned no usable process reading for {pane_id!r}"
    return reading


def _observe_launched_child(*, live: LiveTab, pane_id: str, name: str) -> int:
    """The pid of the single `name` child running under `pane_id`'s retained shell.

    Identified by pid, under the shell herdr calls this pane's own, and owning
    the pane's foreground group. The predecessor polled for the NAME alone and
    then returned whatever reading it last took — including, on expiry, one in
    which the name never appeared, leaving the caller to assert on a reading
    that was never the observation it asked for.
    """
    observed = await_occupying_child(
        read=lambda: process_info_reply(socket_path=live.socket_path, pane_id=pane_id),
        name=name,
        poll=BoundedPoll(seconds=LAUNCH_TIMEOUT),
    )
    assert observed.pid is not None, observed.reason
    return observed.pid


def _start_live_tab(*, session: str, scratch: Path) -> LiveTab:
    """Spawn a detached herdr server and build a tab holding TWO existing panes."""
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
    assert address.exists(), (
        f"herdr session {session!r} never created {address}; "
        f"server log: {(scratch / 'server.log').read_text(errors='replace')[:500]}"
    )
    created = _raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    original = str(created["result"]["root_pane"]["pane_id"])
    # A sibling the operation has no business touching. Split to the RIGHT so it
    # occupies its own column and any vertical reshuffle of the original's column
    # would show up as a change to this pane's own rectangle.
    sibling = _raw_request(
        socket_path=str(address),
        method="pane.split",
        params={
            "pane_id": original,
            "direction": "right",
            "ratio": 0.5,
            "cwd": PANE_CWD,
            "focus": False,
        },
    )
    assert "result" in sibling, f"sibling pane.split failed: {sibling}"
    return LiveTab(
        socket_path=str(address),
        server_pid=child.pid,
        original=original,
        unrelated=str(sibling["result"]["pane"]["pane_id"]),
        transient=startup_transient(scratch=scratch),
    )


def _stop_live_herdr(*, session: str) -> None:
    """Stop and delete ONLY this session, by its exact name."""
    _ = _cli(args=["--session", session, "server", "stop"])
    _ = _cli(args=["session", "delete", session])


@pytest.fixture(name="live")
def _live(*, tmp_path: Path) -> Iterator[LiveTab]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-layout"
    tab = _start_live_tab(session=session, scratch=tmp_path)
    try:
        yield tab
    finally:
        _stop_live_herdr(session=session)


def _modules() -> tuple[Any, Any]:
    for path in (WRITE_CALLS_PATH, WRITER_PATH):
        assert (
            path.is_file()
        ), f"the native herdr layout adapter needs {path.relative_to(PACKAGE_DIR.parent)}"
    return (
        importlib.import_module("herdr_write_calls"),
        importlib.import_module("herdr_write"),
    )


def _target(*, identity: Any, live: LiveTab) -> Any:
    """A qualified target naming the live server's own generation."""
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=live.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    return identity.HerdrPaneTarget(
        socket_path=live.socket_path,
        server_pid=live.server_pid,
        server_starttime=starttime,
        pane_id=live.original,
    )


def _split_top(*, live: LiveTab) -> Any:
    """The real layout sequence, with the created pane's ready shell ESTABLISHED.

    The gate forwards every request to the shipped writer — so the socket, the
    deadline and the peer validation stay against the REAL server whose pid and
    `/proc` start time this target names — and the shell proof it runs with is
    taken from that writer's own fields. Its only effect is to stage and clear a
    real transient startup child between two of the adapter's own requests. The
    `split_window_top` facade this replaces is three lines over the same call
    with the same proof, and the scripted-server tests in
    `tests/test_herdr_layout_exact_target.py` drive it directly.
    """
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    writer = writer_module.HerdrWriter()
    assert hasattr(
        writer, "split_window_top"
    ), "the herdr writer owes a split_window_top placing a retained-shell pane above its target"
    gate = ReadyShellGate(
        inner=writer,
        socket_path=live.socket_path,
        startup_transient=live.transient,
        transient_name=TRANSIENT_NAME,
    )
    outcome = gate.place_above(
        target=_target(identity=identity, live=live),
        cwd=PANE_CWD,
        command=LAUNCH_COMMAND,
        ratio=TOP_RATIO,
    )
    assert gate.refusal() == "", gate.refusal()
    return outcome


def test_the_new_pane_is_placed_above_the_original(*, live: LiveTab):
    """A new pane appears, and it sits strictly ABOVE the pane that was targeted.

    Herdr cannot split upward, so getting this wrong is the natural failure: a
    plain `down` split would leave the daemon BELOW the agent it supervises.
    """
    before, _focused = _geometry(live=live)

    outcome = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    after, _ = _geometry(live=live)
    assert outcome.pane_id not in before, "split_window_top must create a NEW pane"
    assert outcome.pane_id in after, after
    new_top, _new_height = after[outcome.pane_id]
    original_top, _original_height = after[live.original]
    assert new_top < original_top, f"new pane at {new_top} is not above {original_top}"


def test_the_requested_command_runs_in_the_new_pane_s_retained_shell(*, live: LiveTab):
    """The command is the new pane's FOREGROUND process, and its shell survives.

    A retained shell is what makes the pane reusable and keeps it from closing
    when the command exits, so `shell_pid` must be present AND distinct from the
    command's own process group — and the child must be that shell's own, read
    from `/proc`, on the EXACT pane the operation says it created.
    """
    outcome = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    child = _observe_launched_child(live=live, pane_id=outcome.pane_id, name=LAUNCH_NAME)
    reading = _reading(live=live, pane_id=outcome.pane_id)
    assert reading.pane_id == outcome.pane_id, reading
    assert reading.pids_named(name=LAUNCH_NAME) == (child,), reading
    assert reading.shell_pid > 0, reading
    assert reading.is_idle() is False, "the command must run UNDER a retained shell, not replace it"
    assert parent_pid_of(pid=child) == reading.shell_pid, (
        f"the launched process {child} is not a child of the created pane's "
        f"retained shell {reading.shell_pid}"
    )


def test_the_original_pane_keeps_its_identity_and_its_focus(*, live: LiveTab):
    """The supervised session must survive the split completely untouched."""
    before_reading = _reading(live=live, pane_id=live.original)
    _before, focused_before = _geometry(live=live)
    assert focused_before == live.original, "fixture precondition: the original is focused"

    outcome = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    after, focused_after = _geometry(live=live)
    after_reading = _reading(live=live, pane_id=live.original)
    assert live.original in after, "the original pane id must survive"
    assert (
        after_reading.shell_pid == before_reading.shell_pid
    ), "the original pane's shell must not be replaced"
    assert after_reading.is_idle(), f"the original pane was given something to run: {after_reading}"
    assert focused_after == live.original, f"focus moved to {focused_after}"


def test_an_unrelated_pane_is_left_exactly_where_it_was(*, live: LiveTab):
    """Everything else on the tab keeps its geometry and its process identity."""
    before, _focused = _geometry(live=live)
    before_reading = _reading(live=live, pane_id=live.unrelated)

    outcome = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    after, _ = _geometry(live=live)
    after_reading = _reading(live=live, pane_id=live.unrelated)
    assert (
        after[live.unrelated] == before[live.unrelated]
    ), f"unrelated pane moved from {before[live.unrelated]} to {after[live.unrelated]}"
    assert after_reading.shell_pid == before_reading.shell_pid
    assert after_reading.is_idle(), f"the sibling was given something to run: {after_reading}"


def test_the_new_top_pane_takes_the_requested_percentage(*, live: LiveTab):
    """Geometry is a PERCENTAGE of the original pane's column, not a row count.

    `ratio` is the original's share of the split, so after the swap the new top
    pane holds that share — which is what lets a caller ask for "a quarter" and
    get it at any terminal size.
    """
    outcome = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    after, _ = _geometry(live=live)
    _new_top, new_height = after[outcome.pane_id]
    _original_top, original_height = after[live.original]
    column = new_height + original_height
    assert (
        abs(new_height - round(column * TOP_RATIO)) <= 1
    ), f"new pane height {new_height} is not {TOP_RATIO} of the {column}-row column"
