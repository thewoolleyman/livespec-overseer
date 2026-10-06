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

**Every positive launch here runs under a CONTROLLED ready-shell condition, and
that is a repair to this file rather than a convenience.** The pane the command
goes into is created by the adapter and read three round trips later, so what is
in its foreground at that instant is not something fixture setup beforehand can
influence. On the operator host a freshly created pane's `zsh` forks `mise` and
`atuin` while starting, the adapter's pre-launch reading finds the pane
OCCUPIED, and it refuses the launch — correctly. Every test below used to depend
on that startup finishing first, which on this host it did and on the operator's
it did not; the sibling `tests/test_herdr_layout_exact_target.py` recorded the
same refusal as a failure (`w1:p3` occupied by foreground 3618638 rather than
the retained shell 3618552). So `_split_top` now runs the real sequence through
`ReadyShellGate`, which stages a real transient startup child, OBSERVES it, and
then waits for that pane to report an idle retained shell before the adapter's
own reading is taken. A gate that cannot establish that condition fails the
exercise by name — it is never reported as the adapter declining to launch.

Session isolation is herdr's own `--session` mechanism: every session name
carries this test process's pid, and teardown stops and deletes BY THAT EXACT
NAME, so no other session — including the operator's `default` — is touched.
"""

from __future__ import annotations

import importlib
import os
import shutil
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
    ShellIdentityPin,
    await_idle_shell,
    await_occupying_child,
    parent_pid_of,
    process_group_of,
    process_info_reply,
    raw_request,
    read_foreground,
    starttime_of,
    startup_transient,
)

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
# A liveness floor, not a latency budget. Briefly raised to 120.0 on a diagnosis
# that did not hold up: the flake it was meant to address was a wait-predicate
# defect in a sibling file, and the wait below already looked for the intended
# process NAME rather than for the first foreground-group change.
LAUNCH_TIMEOUT = 20.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25

# A trailing `#` comment keeps the marker in the command line the shell echoes
# while leaving an ordinary long-lived `sleep` as the process.
MARKER = "OVLAUNCH1"
LAUNCH_COMMAND = f"sleep 120 #{MARKER}"
LAUNCH_NAME = "sleep"
# Short enough to exit on its own inside the test, which is the "ordinary child
# exit" the pane has to survive — but no shorter than it takes to OBSERVE it
# running. At one second the window was comparable to a scheduling stall, so a
# reading could legitimately arrive after the child was already gone; the test
# below has to identify the child by pid, so its lifetime is a fixture
# requirement rather than a free choice.
BRIEF_SECONDS = 3
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
    transient: str


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _reading(*, socket_path: str, pane_id: str) -> ForegroundReading:
    """`pane_id`'s live process reading, read over a raw socket, or a FIXTURE failure.

    Control evidence must not come from the surface under test, or the file
    would only prove the adapter is self-consistent. An unusable reply stops the
    exercise here rather than raising out of whichever assertion first touched
    a field the server never sent.
    """
    reading = read_foreground(reply=process_info_reply(socket_path=socket_path, pane_id=pane_id))
    assert reading is not None, f"herdr returned no usable process reading for {pane_id!r}"
    return reading


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _pane_ids(*, socket_path: str) -> list[str]:
    reply = raw_request(socket_path=socket_path, method="pane.list", params={})
    return [str(pane["pane_id"]) for pane in reply["result"]["panes"]]


def _observe_launched_child(*, socket_path: str, pane_id: str, name: str) -> int:
    """The pid of the single `name` child running under `pane_id`'s retained shell.

    Identified by pid, under the shell herdr calls this pane's own, and owning
    the pane's foreground group — all three, because a reading that merely
    differs from idle cannot testify about any particular process. A failure to
    observe it is reported with what WAS seen.
    """
    observed = await_occupying_child(
        read=lambda: process_info_reply(socket_path=socket_path, pane_id=pane_id),
        name=name,
        poll=BoundedPoll(seconds=LAUNCH_TIMEOUT),
    )
    assert observed.pid is not None, observed.reason
    return observed.pid


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
    created = raw_request(
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
    reply = raw_request(
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
        yield ServerPair(
            target=target,
            unrelated=unrelated,
            decoy=decoy,
            transient=startup_transient(scratch=tmp_path),
        )
    finally:
        for session in sessions:
            _ = _cli(args=["--session", session, "server", "stop"])
            _ = _cli(args=["session", "delete", session])


def _split_top(*, pair: ServerPair, command: str) -> Any:
    """The real layout sequence, with the created pane's ready shell ESTABLISHED.

    The gate forwards every request to the shipped writer — which keeps the
    socket, the deadline and the peer validation against the REAL server, whose
    pid and `/proc` start time this target names — and the proof it runs with is
    taken from that writer's own fields. Its only effect is to stage and clear a
    real transient startup child between two of the adapter's own requests.
    """
    writer_module = importlib.import_module("herdr_write")
    identity = importlib.import_module("herdr_identity")
    claude_sessions = importlib.import_module("claude_sessions")
    starttime = claude_sessions.proc_starttime(pid=pair.target.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    gate = ReadyShellGate(
        inner=writer_module.HerdrWriter(),
        socket_path=pair.target.socket_path,
        startup_transient=pair.transient,
        transient_name=TRANSIENT_NAME,
    )
    outcome = gate.place_above(
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
    assert gate.refusal() == "", gate.refusal()
    return outcome


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
    child = _observe_launched_child(
        socket_path=pair.target.socket_path, pane_id=outcome.pane_id, name=LAUNCH_NAME
    )
    reading = _reading(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)
    assert reading.shell_pid > 0, reading
    assert (
        reading.group_id != reading.shell_pid
    ), "the command must run UNDER the shell, not replace it"
    assert reading.pids_named(name=LAUNCH_NAME) == (child,), reading
    assert parent_pid_of(pid=child) == reading.shell_pid, (
        f"the launched process {child} is not a child of the verified "
        f"retained shell {reading.shell_pid}"
    )
    text = _capture(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)
    assert MARKER in text, f"the command never reached {outcome.pane_id}: {text!r}"


def _brief_then_busy(*, pair: ServerPair) -> str:
    """The brief child, followed by a REAL post-command process in the SAME shell.

    This is what makes the recovery phase below a genuine observation on any
    host rather than a tautology on a fast one. The operator's `zsh` is still
    running its own post-command work at the instant a child exits — the
    measured reading carried two `zsh` children and a foreground group that was
    not the shell — while a login shell that loads nothing is idle again within
    the same millisecond, so the defect is invisible there. Chaining one real,
    distinctly named, self-terminating process behind the brief child
    reproduces that window under the fixture's control, which is how an
    exercise that infers recovery from the child's exit can be made to fail
    here instead of only on the operator's host.

    The marker comment stays LAST, which is load-bearing and was wrong in the
    first cut: `#` comments to end of line, so `sleep 3 #OVLAUNCH1; <transient>`
    makes the transient part of the comment. It never ran, the shell really was
    idle the instant the child exited, and the sabotage control for this very
    repair passed.
    """
    return f"sleep {BRIEF_SECONDS}; {pair.transient} #{MARKER}"


def _await_child_gone(*, socket_path: str, pane_id: str, child: int) -> str:
    """Wait for `child` to leave BOTH `/proc` and the pane's foreground, or say why not.

    Nothing here signals the child; an ordinary exit is the whole point. The
    bound covers the child's own declared lifetime plus the liveness floor, and
    an expiry is returned as a reason rather than fallen out of silently.
    """
    deadline = time.monotonic() + LAUNCH_TIMEOUT + BRIEF_SECONDS
    reason = "no reading was taken before the deadline"
    while time.monotonic() < deadline:
        reading = _reading(socket_path=socket_path, pane_id=pane_id)
        alive = starttime_of(pid=child)
        listed = child in reading.pids_named(name=LAUNCH_NAME)
        if alive is None and not listed:
            return ""
        reason = (
            f"child {child} is {'still alive' if alive is not None else 'gone from /proc'} "
            f"and {'still listed' if listed else 'unlisted'} in {list(reading.processes)}"
        )
        time.sleep(0.1)
    return f"the brief child {child} never exited on its own within the bound: {reason}"


def test_the_retained_shell_outlives_an_ordinary_child_exit(*, pair: ServerPair):
    """The child is OBSERVED running, then observed gone, then the shell is back.

    A pane whose process exits is closed by herdr, so an `exec`-style launch
    would take the daemon pane down with its first command. The shell must be
    the same shell afterwards and back to owning its own foreground.

    **The chronology is asserted rather than inferred, and that took TWO
    corrections to this test.**

    The first correction retired a `while not _is_idle(info)` loop that followed
    `sleep 1`. That predicate cannot distinguish "the child ran and then exited"
    from "the child was never seen at all": if the first reading lands after a
    one-second child has already finished, the loop body never runs and every
    assertion still passes, reporting a child exit nothing observed. Measured
    natively rather than argued — with a declared 1.5s stall injected between
    the launch and the first reading, the loop body ran 0 times in 4 of 4
    rounds, no reading it took contained the `sleep` child, and the old
    assertions still reported idle-and-same-shell. Without the stall the old
    predicate was no better AS EVIDENCE: in 8 of 8 rounds the child's pid was
    inside the loop's field of view, and the loop consulted only the foreground
    group id — which commit 58d35c73 already measured leaving the shell while
    the child is still `bash`, before the exec.

    **The second correction is that the child's exit is not the shell's
    recovery, and this test used to read one off the other.** Having waited for
    the child to disappear, it asserted idleness on the reading taken at that
    same instant. Measured on the operator host, that reading still carried two
    `zsh` children and a foreground group that was not the shell — so the
    assertion failed on a condition that had simply not happened YET. Recovery
    is its own observation with its own bounded wait, and an unrecovered shell
    is reported as such. The launched command carries a real post-command
    process for the reason `_brief_then_busy` records: without it this host is
    idle again instantly and the correction cannot be exercised at all.

    So each of the three phases is waited for AND asserted:

      1. the child, identified by pid, with the verified retained shell as its
         `/proc` parent and a process group of its own;
      2. that same pid gone from both `/proc` and the pane's foreground, with
         no signal sent by this test — an ordinary exit, not a kill;
      3. SEPARATELY, and within its own bound, the same shell — same pid AND
         same start time, so a replacement at a recycled pid cannot pass —
         owning its foreground again, pane still open.
    """
    outcome = _split_top(pair=pair, command=_brief_then_busy(pair=pair))

    assert outcome.ok is True, outcome.error
    before = _reading(socket_path=pair.target.socket_path, pane_id=outcome.pane_id).shell_pid
    before_starttime = starttime_of(pid=before)
    assert before_starttime is not None, f"the retained shell {before} must be alive to begin with"

    child = _observe_launched_child(
        socket_path=pair.target.socket_path, pane_id=outcome.pane_id, name=LAUNCH_NAME
    )
    assert (
        parent_pid_of(pid=child) == before
    ), f"the brief child {child} is not a child of the verified retained shell {before}"
    assert (
        process_group_of(pid=child) != before
    ), "the brief child must run in its OWN process group, not as the shell itself"

    departed = _await_child_gone(
        socket_path=pair.target.socket_path, pane_id=outcome.pane_id, child=child
    )
    assert departed == "", departed

    recovery = await_idle_shell(
        read=lambda: process_info_reply(
            socket_path=pair.target.socket_path, pane_id=outcome.pane_id
        ),
        pane_id=outcome.pane_id,
        poll=BoundedPoll(seconds=LAUNCH_TIMEOUT),
        expected=ShellIdentityPin(pid=before, starttime=before_starttime),
    )
    assert recovery.recovered is True, recovery.reason
    assert outcome.pane_id in _pane_ids(
        socket_path=pair.target.socket_path
    ), "the pane must survive its command finishing"


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
        reading = _reading(socket_path=socket_path, pane_id=pane_id)
        assert reading.is_idle(), f"{pane_id} was given something to run: {reading}"
        assert MARKER not in _capture(
            socket_path=socket_path, pane_id=pane_id
        ), f"the command text reached {pane_id}"
