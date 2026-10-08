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

The staged transient is a bounded DISCRIMINATING instance, not a claim to have
reproduced the host's startup: these tests passed before the change and pass
after it, as PRESERVATION controls over guards that already hold, and none of
this is a product Red. `tests/test_herdr_live_observations.py` carries that
framing in full.

Session isolation is herdr's own `--session` mechanism: every session name
carries this test process's pid, and teardown stops and deletes BY THAT EXACT
NAME, so no other session — including the operator's `default` — is touched.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_sessions
import herdr_identity
import herdr_write
import pytest
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    BoundedPoll,
    ForegroundReading,
    PaneIdentity,
    PaneReadiness,
    ReadyWriter,
    RegisteredShell,
    ShellIdentityPin,
    await_coherent_identity,
    await_idle_shell,
    await_occupying_child,
    pane_capture,
    pane_ids,
    parent_pid_of,
    process_group_of,
    process_info_reply,
    read_foreground,
    registered_login_shells,
    run_in_pane,
    split_pane,
    start_owned_server,
    starttime_of,
    startup_transient,
    stop_owned_server,
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
# A bound short enough to expire WHILE the staged post-command process is still
# running, and long enough to take several real readings first. The transient
# outlives it by well over a second, so the refusal it proves is about the
# shell's state rather than about which of two timers won.
IMPATIENT_BOUND = 0.3
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
    # The FIXTURE's own reading of the host login-shell register, used only to
    # establish the created pane's identity premise. It is never handed to the
    # adapter, whose own `shell_aliases` is what these exercises grade.
    registered: tuple[RegisteredShell, ...] = ()


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
    """One OWNED server, started through the shared seam, plus its root pane.

    The shared seam is what makes the shell this server's panes run a DECLARED
    fixture choice rather than an inherited one; see
    `test_herdr_live_observations.start_owned_server`.
    """
    owned = start_owned_server(session=session, scratch=scratch, log_name=log_name, cwd=PANE_CWD)
    return LiveServer(
        session=session,
        socket_path=owned.socket_path,
        server_pid=owned.server_pid,
        root=owned.root,
    )


def _split(*, server: LiveServer, pane_id: str, direction: str) -> str:
    return split_pane(socket_path=server.socket_path, pane_id=pane_id, direction=direction)


@pytest.fixture(name="pair")
def _pair(*, tmp_path: Path) -> Iterator[ServerPair]:
    """Two OWNED servers, each cleaned up by name whatever the setup does.

    The second server's panes are built AFTER the first exists, so a failure
    anywhere in that build used to leave the first running. Both sessions are
    registered before anything can fail and torn down in one `finally`.
    """
    sessions = (
        f"overseer-test-{os.getpid()}-launch-target",
        f"overseer-test-{os.getpid()}-launch-decoy",
    )
    try:
        target = _start_server(session=sessions[0], scratch=tmp_path, log_name="target.log")
        unrelated = _split(server=target, pane_id=target.root, direction="right")
        decoy = _start_server(session=sessions[1], scratch=tmp_path, log_name="decoy.log")
        latest = decoy.root
        for _ in range(DECOY_PANES - 1):
            latest = _split(server=decoy, pane_id=latest, direction="right")
        yield ServerPair(
            target=target,
            unrelated=unrelated,
            decoy=decoy,
            transient=startup_transient(scratch=tmp_path),
            registered=registered_login_shells(),
        )
    finally:
        for session in sessions:
            stop_owned_server(session=session)


def _split_top(*, pair: ServerPair, command: str) -> tuple[Any, PaneReadiness]:
    """The writer's own PUBLIC entrypoint, with the created pane's readiness ESTABLISHED.

    **This enters `HerdrWriter.split_window_top` rather than
    `herdr_layout.place_above`, and that is the repair.** The facade is part of what
    these exercises are about; a sequence entered one layer below it is a different
    subject, and reducing the coverage to the internal layout call is exactly what the
    inherited-facade assertion below prevents from happening silently again.

    The seam is `ReadyWriter` — the shipped writer with its PUBLIC `request` interposed
    — so the socket, the per-request deadline, the peer revalidation against the REAL
    server whose pid and `/proc` start time this target names, and the `ShellProof`
    built from the writer's own fields are all the shipped facade's. Its only effect is
    to establish the EXACT created pane's available and coherent identity between two
    of the writer's own requests, where it costs no request its deadline.

    The readiness is returned alongside the outcome because an unestablished or expired
    premise has to be gradeable as a FIXTURE failure by every caller.
    """
    starttime = claude_sessions.proc_starttime(pid=pair.target.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    assert (
        ReadyWriter.split_window_top is herdr_write.HerdrWriter.split_window_top
    ), "the exercise must enter the SHIPPED public facade, not a fixture reimplementation"
    readiness = PaneReadiness(
        socket_path=pair.target.socket_path, transient=pair.transient, registered=pair.registered
    )
    outcome = ReadyWriter(readiness=readiness).split_window_top(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=pair.target.socket_path,
            server_pid=pair.target.server_pid,
            server_starttime=starttime,
            pane_id=pair.target.root,
        ),
        cwd=PANE_CWD,
        command=command,
        ratio=TOP_RATIO,
    )
    return outcome, readiness


def _established(*, readiness: PaneReadiness, pane_id: str) -> PaneIdentity:
    """Grade the created pane's readiness premise before anything grades the adapter.

    Every fact separately, so a failure says which one was missing: the step ran
    exactly once and for the pane the writer reported creating, the gate established
    what it establishes, the controlled child was the pinned shell's own, it exited,
    that shell recovered, and the pane's two shell descriptions agree about it. An
    unavailable or contradictory observation therefore fails HERE, carrying the bound
    it expired under, and is never reported as the adapter declining a launch.
    """
    assert readiness.panes == [pane_id], (
        "readiness must have been established exactly once, for the pane the writer created; "
        f"it ran for {readiness.panes} against {pane_id!r} while the writer sent "
        f"{readiness.methods()}"
    )
    assert readiness.refusal() == "", f"{pane_id!r} readiness: {readiness.refusal()}"
    gate = readiness.gate
    assert gate is not None, "a refusal-free run established something, so it must hold a gate"
    staged = gate.transient
    assert staged is not None and staged.pid is not None, staged
    assert gate.retained is not None, "the created pane's retained shell was never pinned"
    assert parent_pid_of(pid=staged.pid) in (None, gate.retained.pid), (
        f"the controlled child {staged.pid} is not a child of the pinned retained "
        f"shell {gate.retained.pid}"
    )
    assert gate.departed == "", gate.departed
    recovery = gate.established
    assert recovery is not None and recovery.recovered is True, recovery
    identity = readiness.identity
    assert identity is not None and identity.coherent is True, readiness.refusal()
    assert identity.shell_pid == gate.retained.pid, (
        f"the coherent identity describes shell {identity.shell_pid} while the pinned retained "
        f"shell is {gate.retained.pid}"
    )
    assert readiness.methods().count("pane.process_info") == 2, (
        "the writer must still take BOTH of its own readings — the establish and the recheck: "
        f"{readiness.methods()}"
    )
    return identity


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
    outcome, readiness = _split_top(pair=pair, command=LAUNCH_COMMAND)

    assert outcome.ok is True, outcome.error
    identity = _established(readiness=readiness, pane_id=outcome.pane_id)
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
    # The SAME retained shell the readiness premise was established on, not merely
    # whichever shell the pane reported afterwards: without this the launch could be
    # running under a replacement and every assertion above would still hold.
    assert reading.shell_pid == identity.shell_pid, (
        f"the command runs under shell {reading.shell_pid}, not the established retained "
        f"shell {identity.shell_pid}"
    )
    assert readiness.deliveries() == [
        (outcome.pane_id, LAUNCH_COMMAND, ("Enter",))
    ], readiness.deliveries()
    text = pane_capture(socket_path=pair.target.socket_path, pane_id=outcome.pane_id)
    assert MARKER in text, f"the command never reached {outcome.pane_id}: {text!r}"


def _brief_then_busy(*, pair: ServerPair) -> str:
    """The brief child, followed by a REAL post-command process in the SAME shell.

    This is what makes the recovery phase below a genuine observation on any
    host rather than a tautology on a fast one. The operator's `zsh` is still
    running its own post-command work at the instant a child exits — the
    measured reading carried two `zsh` children and a foreground group that was
    not the shell — while a login shell that loads nothing is idle again within
    the same millisecond, so the window is simply absent there and the exercise
    passes without ever exercising its own recovery wait.

    Chaining one real, distinctly named, self-terminating process behind the
    brief child stages a BOUNDED DISCRIMINATING INSTANCE of that window under
    the fixture's control. It is deliberately the weaker claim: this is not a
    reproduction of the operator's `zsh` post-command work, and the pass this
    file records here is not a reproduced host failure. What it discriminates is
    whether recovery was WAITED FOR or merely inherited from a shell that was
    never busy — which is the premise the repair is about.

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
    outcome, readiness = _split_top(pair=pair, command=_brief_then_busy(pair=pair))

    assert outcome.ok is True, outcome.error
    _ = _established(readiness=readiness, pane_id=outcome.pane_id)
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
    assert outcome.pane_id in pane_ids(
        socket_path=pair.target.socket_path
    ), "the pane must survive its command finishing"


def test_a_child_exit_before_shell_idle_is_a_bounded_discriminating_case(*, pair: ServerPair):
    """The window the recovery wait exists for, OBSERVED on every run.

    The exercise above stages this window and then waits it out, which proves
    the wait does not BREAK anything — but on a host where the window is absent
    it would pass just as happily with no wait at all. A temporary sabotage
    showed the difference once; nothing kept showing it. This control does,
    permanently, and it drives the delivered helper rather than the adapter:
    the layout sequence is not involved at all, so a refusal here is
    unambiguously about the observation.

    Three bounded steps, each a real reading from the real server:

      1. the requested child is observed, and then observed GONE from both
         `/proc` and the pane's foreground, unsignalled;
      2. a real post-command process is then observed owning that pane's
         foreground — POSITIVE evidence that the shell was not idle after its
         child exited, rather than an inference from a gap;
      3. so `await_idle_shell` under a short bound REFUSES while that process
         runs, and the bound this file actually uses then recovers the same
         shell identity.

    Step 3 is what a predecessor could not have passed: it asserted idleness on
    the reading taken at step 1 and would read step 2's as a failed recovery.
    """
    pane_id = _split(server=pair.target, pane_id=pair.unrelated, direction="down")

    def read() -> dict[str, Any]:
        return process_info_reply(socket_path=pair.target.socket_path, pane_id=pane_id)

    # THE RAW-SPLIT DIRECT OBSERVATION CONTROL, and the measured failure it carries.
    # This used to read the pane's process info IMMEDIATELY after the split, with no
    # wait behind it, and assert the reading was usable. On the operator host that
    # reading carried no usable native fields at all and the exercise failed here —
    # before it entered the layout adapter, on its own fixture premise. The exact
    # pane is knowable at this boundary because this exercise split it itself, so the
    # fix is a BOUNDED establishment of that pane's available and coherent identity:
    # a one-shot unusable reading is consumed and retried, and a persistently
    # unavailable or contradictory one expires as a NAMED fixture refusal.
    identity = await_coherent_identity(
        read=read,
        pane_id=pane_id,
        poll=BoundedPoll(seconds=LAUNCH_TIMEOUT),
        registered=pair.registered,
    )
    assert identity.coherent is True, identity.reason
    shell = identity.shell_pid
    starttime = starttime_of(pid=shell)
    assert starttime is not None, f"the pane's shell {shell} must be alive to begin with"
    pin = ShellIdentityPin(pid=shell, starttime=starttime)

    run_in_pane(
        socket_path=pair.target.socket_path, pane_id=pane_id, command=_brief_then_busy(pair=pair)
    )
    child = _observe_launched_child(
        socket_path=pair.target.socket_path, pane_id=pane_id, name=LAUNCH_NAME
    )
    departed = _await_child_gone(socket_path=pair.target.socket_path, pane_id=pane_id, child=child)
    assert departed == "", departed

    busy = await_occupying_child(
        read=read, name=TRANSIENT_NAME, poll=BoundedPoll(seconds=LAUNCH_TIMEOUT)
    )
    assert busy.pid is not None, (
        f"the shell was already idle after child {child} exited, so this control staged "
        f"no window to discriminate: {busy.reason}"
    )

    impatient = await_idle_shell(
        read=read, pane_id=pane_id, poll=BoundedPoll(seconds=IMPATIENT_BOUND), expected=pin
    )
    assert impatient.recovered is False, (
        f"recovery was reported while {TRANSIENT_NAME} {busy.pid} still owned the "
        f"foreground of {pane_id!r}"
    )
    assert "is not the shell" in impatient.reason, impatient.reason

    recovery = await_idle_shell(
        read=read, pane_id=pane_id, poll=BoundedPoll(seconds=LAUNCH_TIMEOUT), expected=pin
    )
    assert recovery.recovered is True, recovery.reason


def test_no_other_pane_on_either_server_receives_the_launch(*, pair: ServerPair):
    """The supervised pane, the bystander, and another server's same-ID panes.

    The decoy server deliberately holds a pane with the id the command was
    written to, so "it went to the right pane" is a claim about instance
    routing and not just about a string.
    """
    outcome, readiness = _split_top(pair=pair, command=LAUNCH_COMMAND)

    assert outcome.ok is True, outcome.error
    identity = _established(readiness=readiness, pane_id=outcome.pane_id)
    decoy_panes = pane_ids(socket_path=pair.decoy.socket_path)
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
    assert pair.decoy.server_pid != pair.target.server_pid, "fixture precondition: two servers"
    for socket_path, pane_id in untouched:
        reading = _reading(socket_path=socket_path, pane_id=pane_id)
        assert reading.is_idle(), f"{pane_id} was given something to run: {reading}"
        # Distinct SHELL PROCESSES, not merely distinct id strings. Herdr pane ids are
        # unique only within a server, so the decoy holds panes named exactly like the
        # target's; a reading that happened to be about the wrong instance would carry
        # the established created pane's own shell and pass every other assertion here.
        assert reading.shell_pid != identity.shell_pid, (
            f"{pane_id} on {socket_path} reports shell {reading.shell_pid}, which is the "
            "created pane's own established retained shell, so these are not separate panes"
        )
        assert MARKER not in pane_capture(
            socket_path=socket_path, pane_id=pane_id
        ), f"the command text reached {pane_id}"
