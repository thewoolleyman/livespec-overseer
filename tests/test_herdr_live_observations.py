"""Bounded native OBSERVATIONS the herdr exercises establish preconditions with.

Every native exercise in this tree has to establish a fact about a REAL pane
before it may assert anything about the adapter: that a requested child is
running under that pane's retained shell, or that the shell owns an idle
foreground. Each exercise open-coded those two observations, and every copy was
wrong in the SAME direction — it reported an established precondition on
evidence that did not support one. The helpers here are the single honest
answer, and the controls in this file are what keep them honest.

**Where the evidence comes from, and what this tree can and cannot witness.**
The four defects below were measured against real herdr ON THE OPERATOR HOST and
are supplied with the work item; they are fixture-premise failures, not evidence
about the adapter. The sandbox these exercises also run in has a login shell that
loads nothing, so the pre-existing native exercises PASS here and always did —
they are PRESERVATION CONTROLS over guards that already hold, and nothing in this
file relabels them as a reproduced host failure or as a product Red. No guarded
product code changed for any of it; what changed is the fixtures' premises and
the controls that discriminate them.

**That sandbox/host gap has a SECOND leg, and the fifth defect fell straight
through it.** The sandbox's `sleep` is a GNU standalone binary while the
operator host's is a uutils MULTICALL executable, so a transient built by
renaming `sleep` ran perfectly here and could not run there at all. A native
exercise passing in this sandbox is therefore evidence about this sandbox's
coreutils as well as about its login shell. Where a property turns on either,
the discriminating control is a DISCLOSED MECHANISM staged by this file, and the
real boundary stays a HOST assertion that no run here discharges.

**The four measured fixture defects these replace.** All four were taken against
real herdr on the operator host, and none of them is evidence about the adapter.
A FIFTH, measured on the same host against the repair itself, is recorded further
down — see "the transient's portability control" and `startup_transient`.

  - **A transient startup process satisfied the occupation wait.** The old wait
    returned as soon as a pane's `foreground_process_group_id` differed from its
    `shell_pid` — any difference, by any process. Measured: shell `zsh` pid
    3584980, then foreground pid 3585294 named `mv`, a child of the operator
    shell's own startup. The wait returned immediately and the requested `sleep`
    was never observed, so the pane the adapter then read was genuinely IDLE and
    it returned `outcome.ok=True` — correctly. The exercise's expected-refusal
    assertion therefore **FAILED**.

    **Note the direction, because the obvious reading of that is backwards.**
    This was a FAILING test against a CORRECT product, not a passing test hiding
    a defect: the fixture never staged an occupant, so the run says nothing
    whatever about whether the adapter would accept a PROVEN occupied pane. A
    false premise produced a false accusation. What the repair buys is that the
    same false premise now fails as a FIXTURE failure, naming what it saw.
  - **A reading missing a field raised instead of refusing.** Another real run
    raised `KeyError: 'foreground_process_group_id'` inside the setup thread,
    where nothing was watching for it.
  - **A setup TIMEOUT was indistinguishable from success.** The same loop simply
    fell out at its deadline and returned `None`, after which the caller stamped
    its precondition flag anyway.
  - **Idle recovery was INFERRED from a child's exit.** The lifecycle exercise
    waited for its child to disappear and then asserted idleness in the same
    breath; the reading taken at that instant still carried two `zsh` children
    and a foreground group that was not the shell. The child exiting is not the
    shell recovering, and only one of the two was ever waited for.

**So every helper here answers with a REASON rather than a bool, and a deadline
is a failure.** `read_foreground` turns an unusable reply into an unsuccessful
observation instead of an exception; `occupying_child_pid` requires the
REQUESTED name, the retained shell as the child's `/proc` parent, and the pane's
own foreground group; `await_idle_shell` waits for idleness as its own separate
observation and, when pinned, for the same shell IDENTITY rather than the same
pid. Nothing here sleeps to wait out a race — each loop polls a real reading
under a bound it reports when it expires.

`ReadyShellGate` is the write-side counterpart, and it enters the adapter at
:func:`herdr_layout.place_above` rather than at `HerdrWriter.split_window_top`.
That is deliberate: the pane whose shell has to be ready is one the ADAPTER
creates, three round trips before it is written to, so no amount of fixture
setup beforehand can establish anything about it. The gate is a transparent
`BoundedRequests` that forwards every request to the real writer — which keeps
the socket, the deadline and the peer validation against the REAL herdr server,
rather than against a proxy this test process owns — and whose only effect is to
run the establishment step BETWEEN two of the adapter's own requests, where it
costs no request its deadline. `split_window_top` is the three-line facade over
the same call with the same proof, and it is driven by the scripted-server tests
in `tests/test_herdr_layout_exact_target.py`.
"""

from __future__ import annotations

import importlib
import json
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

__all__: list[str] = [
    "BoundedPoll",
    "ChildObservation",
    "ForegroundReading",
    "ReadyShellGate",
    "ShellIdentityPin",
    "ShellRecovery",
    "await_idle_shell",
    "await_occupying_child",
    "occupying_child_pid",
    "parent_pid_of",
    "process_group_of",
    "process_info_reply",
    "raw_request",
    "read_foreground",
    "starttime_of",
    "startup_transient",
]

POLL_SECONDS = 0.1
READY_TIMEOUT = 30.0
PidReader = Callable[..., int | None]

# The CONTROLLED startup transient every exercise stages, instead of depending
# on whatever the operator's login shell happens to load. A distinct name is the
# whole point: it is a real process with a real `/proc` lineage that is
# unmistakably not the child any exercise requested.
TRANSIENT_NAME = "ovstartup"
TRANSIENT_SECONDS = 2
# PR_SET_NAME, from `linux/prctl.h`. The transient names ITSELF, so the name the
# kernel reports — and therefore the name herdr reports, which it reads from
# `/proc/<pid>/comm` — comes from a call this fixture makes rather than from the
# basename of a renamed binary. The script verifies the rename took effect and
# exits loudly if it did not, so a platform where `prctl` is unavailable fails as
# itself instead of as an unobserved child.
_PR_SET_NAME = 15
_TRANSIENT_SOURCE = f'''\
"""One real, bounded, SELF-NAMED foreground child for the native herdr exercises.

Written by `startup_transient` in tests/test_herdr_live_observations.py; see that
function for why the name is set here rather than taken from a file name.
"""

import ctypes
import pathlib
import sys
import time

_ = ctypes.CDLL(None, use_errno=True).prctl({_PR_SET_NAME}, b"{TRANSIENT_NAME}", 0, 0, 0)
_named = pathlib.Path("/proc/self/comm").read_text(encoding="utf-8").strip()
if _named != "{TRANSIENT_NAME}":
    raise SystemExit(f"prctl(PR_SET_NAME) left this process named {{_named!r}}")
time.sleep(float(sys.argv[1]))
'''


def startup_transient(*, scratch: Path) -> str:
    """A command that runs one real, self-terminating foreground child.

    A short Python script run by THIS interpreter under its own real path, which
    renames itself to :data:`TRANSIENT_NAME` and then sleeps for the argument it
    is given. The process the kernel reports is genuine, and its lifetime is this
    fixture's to choose rather than the host's. It stands in for the `mise` and
    `atuin` children the operator's `zsh` forks while a freshly created pane
    starts up — the measured condition under which the adapter legitimately
    refuses a launch.

    **Why the child names itself instead of being a renamed `sleep`.** This used
    to copy `shutil.which("sleep")` to a file called `ovstartup` and run that.
    A standalone `sleep` does not care what it is called, so it worked in the
    factory sandbox and in CI — but the operator host's `sleep` is a MULTICALL
    executable (uutils coreutils), which decides which utility to BE from the
    name it was invoked under. Under the name `ovstartup` it recognized no
    utility, fell back to reading its first argument as one, printed
    `<arg>: function/utility not found` and exited 1 without ever sleeping, so
    every native exercise that staged a transient failed on its own fixture
    premise. The receipts, and the disclosed-mechanism control over this
    property, are in
    `test_the_startup_transient_runs_where_sleep_dispatches_on_its_invocation_name`
    below.

    So the identity and the lifetime no longer rest on renaming a system utility
    at all: nothing here consults `PATH`, the interpreter is invoked by the
    absolute path it already runs under, and the name is a `prctl` this fixture
    makes.
    """
    assert sys.executable, "a native exercise needs a real interpreter path to run"
    script = scratch / f"{TRANSIENT_NAME}.py"
    _ = script.write_text(_TRANSIENT_SOURCE, encoding="utf-8")
    return f"{sys.executable} {script} {TRANSIENT_SECONDS}"


# ------------------------------------------------------------------ readings


@dataclass(frozen=True, kw_only=True)
class ForegroundReading:
    """One `pane.process_info` reply reduced to the facts an exercise needs.

    Constructed only by :func:`read_foreground`, so every instance is a reading
    whose required fields were actually present — a reading that exists is
    usable, and an unusable reply is an absent reading rather than a partially
    filled one.
    """

    pane_id: str
    shell_pid: int
    group_id: int
    processes: tuple[tuple[int, str], ...]

    def is_idle(self) -> bool:
        """Whether the pane's own retained shell owns its foreground group."""
        return self.group_id == self.shell_pid

    def pids_named(self, *, name: str) -> tuple[int, ...]:
        return tuple(pid for pid, listed in self.processes if listed == name)


def _as_int(*, value: object) -> int | None:
    """`value` when it is a genuine JSON integer, else None.

    `bool` is excluded deliberately: it is an `int` subclass, so a server (or a
    scripted reply) answering `true` would otherwise read as the pid 1.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _listed_processes(*, entries: object) -> tuple[tuple[int, str], ...]:
    """The `(pid, name)` pairs a reply's `foreground_processes` carries.

    Entries without a readable pid are dropped rather than refused: the LIST is
    descriptive, and the two fields the observation actually turns on —
    `shell_pid` and `foreground_process_group_id` — are required by
    :func:`read_foreground` itself.
    """
    if not isinstance(entries, list):
        return ()
    listed: list[tuple[int, str]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        pid = _as_int(value=entry.get("pid"))
        if pid is not None:
            listed.append((pid, str(entry.get("name"))))
    return tuple(listed)


def read_foreground(*, reply: Mapping[str, Any]) -> ForegroundReading | None:
    """`reply`'s process reading, or None when the server supplied no usable one.

    None is an UNSUCCESSFUL OBSERVATION, never an exception. A missing envelope,
    a missing `process_info`, or either required field absent all mean the same
    thing to a caller — this reading cannot establish anything — and the old
    open-coded `info["foreground_process_group_id"]` turned that into a
    `KeyError` raised in a setup thread where nothing could see it.
    """
    result = reply.get("result")
    info = result.get("process_info") if isinstance(result, Mapping) else None
    if not isinstance(info, Mapping):
        return None
    shell_pid = _as_int(value=info.get("shell_pid"))
    group_id = _as_int(value=info.get("foreground_process_group_id"))
    if shell_pid is None or group_id is None:
        return None
    return ForegroundReading(
        pane_id=str(info.get("pane_id", "")),
        shell_pid=shell_pid,
        group_id=group_id,
        processes=_listed_processes(entries=info.get("foreground_processes")),
    )


# -------------------------------------------------------------- /proc readers


def _stat_fields(*, pid: int) -> list[str] | None:
    """`pid`'s post-comm `/proc/<pid>/stat` fields, or None when the pid is gone.

    The comm field can contain spaces and parentheses, so the fields after it
    are taken from the LAST close parenthesis rather than by splitting the whole
    line. Absence is returned rather than raised because a child disappearing
    IS one of the observations these exercises make.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    return stat[stat.rindex(")") + 1 :].split()


def parent_pid_of(*, pid: int) -> int | None:
    """`pid`'s parent, read from `/proc` — the one place the lineage is a FACT."""
    fields = _stat_fields(pid=pid)
    return None if fields is None else int(fields[1])


def process_group_of(*, pid: int) -> int | None:
    """`pid`'s own process group, from `/proc`."""
    fields = _stat_fields(pid=pid)
    return None if fields is None else int(fields[2])


def starttime_of(*, pid: int) -> int | None:
    """`pid`'s start time in clock ticks, or None when the pid is gone.

    Carried alongside a pid so "the SAME shell" is a claim about an IDENTITY
    rather than about an integer: a pid can be recycled, a pid paired with its
    start time cannot be.
    """
    # `stat` field 22 counted from one; field 3 (`state`) is this list's index 0,
    # so the offset is three. Verified against `awk '{print $22}'` on this host.
    fields = _stat_fields(pid=pid)
    return None if fields is None else int(fields[19])


# ------------------------------------------------------------- the two waits


@dataclass(frozen=True, kw_only=True)
class BoundedPoll:
    """The bound and the clock a native observation runs under.

    The clock and the sleep are injectable so the deadline branch can be driven
    deterministically — a timeout control that really waited would be a slow
    test asserting a timer rather than the reported outcome.
    """

    seconds: float
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


@dataclass(frozen=True, kw_only=True)
class ChildObservation:
    """The requested child as OBSERVED, or the reason it was not observed.

    `pid` is None on every refusal and `reason` is empty on every success, so a
    caller cannot read an unestablished observation as an established one.
    """

    pid: int | None
    reason: str


@dataclass(frozen=True, kw_only=True)
class ShellIdentityPin:
    """A shell as an identity: its pid AND the start time recorded beside it."""

    pid: int
    starttime: int


@dataclass(frozen=True, kw_only=True)
class ShellRecovery:
    """Whether the pane reached an idle retained shell, or why it had not."""

    recovered: bool
    reason: str


def occupying_child_pid(
    *,
    reading: ForegroundReading,
    name: str,
    parent_of: PidReader = parent_pid_of,
    group_of: PidReader = process_group_of,
) -> ChildObservation:
    """`reading`'s requested foreground child, under the retained shell, or why not.

    Four conditions, all required, because dropping any one of them is how a
    fixture comes to report an occupation it never saw:

      1. the pane's foreground group has LEFT its shell — the only condition the
         old wait checked, and the one a transient startup process satisfies;
      2. exactly one foreground process carries the REQUESTED name, so an
         unrelated `mv` from shell startup is not mistaken for a `sleep` nobody
         ever observed;
      3. the child's `/proc` parent is this pane's `shell_pid`, which is what
         "under the retained shell" means and what an `exec`-replaced shell
         cannot show;
      4. the child's own process group IS the pane's foreground group, so a
         process merely listed beside the foreground cannot stand in for it.
    """
    if reading.is_idle():
        return ChildObservation(
            pid=None,
            reason=(
                f"{reading.pane_id!r} foreground group {reading.group_id} is still its "
                f"shell {reading.shell_pid}, so no child owns it"
            ),
        )
    candidates = reading.pids_named(name=name)
    if len(candidates) != 1:
        return ChildObservation(
            pid=None,
            reason=(
                f"{reading.pane_id!r} holds {len(candidates)} foreground process(es) named "
                f"{name!r}; its foreground is {list(reading.processes)}"
            ),
        )
    child = candidates[0]
    parent = parent_of(pid=child)
    if parent != reading.shell_pid:
        return ChildObservation(
            pid=None,
            reason=(
                f"foreground {name!r} {child} reports parent {parent}, not the retained "
                f"shell {reading.shell_pid} of {reading.pane_id!r}"
            ),
        )
    group = group_of(pid=child)
    if group != reading.group_id:
        return ChildObservation(
            pid=None,
            reason=(
                f"foreground {name!r} {child} runs in process group {group}, not the pane's "
                f"foreground group {reading.group_id}"
            ),
        )
    return ChildObservation(pid=child, reason="")


def await_occupying_child(
    *,
    read: Callable[[], Mapping[str, Any]],
    name: str,
    poll: BoundedPoll,
    parent_of: PidReader = parent_pid_of,
    group_of: PidReader = process_group_of,
) -> ChildObservation:
    """Poll real readings until the requested child is observed, or report why not.

    The expiry is REPORTED. The predecessor returned silently at its deadline,
    which left the caller unable to tell a setup timeout from an established
    precondition — and the caller stamped the precondition either way.
    """
    deadline = poll.monotonic() + poll.seconds
    reason = "no process reading was taken before the deadline"
    while poll.monotonic() < deadline:
        reading = read_foreground(reply=read())
        if reading is None:
            reason = "the herdr process reading carried no usable shell/foreground fields"
        else:
            observed = occupying_child_pid(
                reading=reading, name=name, parent_of=parent_of, group_of=group_of
            )
            if observed.pid is not None:
                return observed
            reason = observed.reason
        poll.sleep(POLL_SECONDS)
    return ChildObservation(
        pid=None,
        reason=f"no {name!r} child was observed within {poll.seconds}s: {reason}",
    )


def _recovery_refusal(
    *,
    reading: ForegroundReading | None,
    pane_id: str,
    expected: ShellIdentityPin | None,
    starttime_of_pid: PidReader,
) -> str:
    """Why `reading` is not yet an idle retained shell for `pane_id`, or ``""``."""
    if reading is None:
        return "the herdr process reading carried no usable shell/foreground fields"
    if reading.pane_id != pane_id:
        return f"the reading describes pane {reading.pane_id!r}, not {pane_id!r}"
    if expected is not None and reading.shell_pid != expected.pid:
        return f"the pane now holds shell {reading.shell_pid}, not {expected.pid}"
    if expected is not None and starttime_of_pid(pid=expected.pid) != expected.starttime:
        return (
            f"shell {expected.pid} no longer carries start time {expected.starttime}, so a "
            "DIFFERENT process holds that pid"
        )
    if not reading.is_idle():
        return (
            f"foreground group {reading.group_id} is not the shell {reading.shell_pid}; "
            f"its foreground is {list(reading.processes)}"
        )
    return ""


def await_idle_shell(
    *,
    read: Callable[[], Mapping[str, Any]],
    pane_id: str,
    poll: BoundedPoll,
    expected: ShellIdentityPin | None = None,
    starttime_of_pid: PidReader = starttime_of,
) -> ShellRecovery:
    """Wait for `pane_id` to report an idle retained shell, within the bound.

    Used for both halves of the same question. With `expected` unset it
    ESTABLISHES readiness — the condition the adapter's own pre-launch reading
    requires, which a pane whose shell is still running its startup does not yet
    satisfy. With `expected` set it proves RECOVERY, and the pin is a pid with
    its start time so a replacement arriving at a recycled pid cannot pass.
    """
    deadline = poll.monotonic() + poll.seconds
    reason = "no process reading was taken before the deadline"
    while poll.monotonic() < deadline:
        reason = _recovery_refusal(
            reading=read_foreground(reply=read()),
            pane_id=pane_id,
            expected=expected,
            starttime_of_pid=starttime_of_pid,
        )
        if not reason:
            return ShellRecovery(recovered=True, reason="")
        poll.sleep(POLL_SECONDS)
    return ShellRecovery(
        recovered=False,
        reason=(
            f"{pane_id!r} never reported an idle retained shell within {poll.seconds}s: {reason}"
        ),
    )


# ------------------------------------------------------------- the raw socket


def _read_frame(*, conn: socket.socket) -> bytes:
    buffered = b""
    while not buffered.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        buffered += chunk
    return buffered


def raw_request(*, socket_path: str, method: str, params: dict[str, object]) -> dict[str, Any]:
    """One raw round trip to the REAL server, for setup and for control facts.

    Control evidence must not come from the surface under test, or an exercise
    would only prove the adapter is self-consistent.
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(15.0)
    sock.connect(socket_path)
    sock.sendall(json.dumps({"id": "fixture", "method": method, "params": params}).encode() + b"\n")
    try:
        answered = _read_frame(conn=sock)
    finally:
        sock.close()
    parsed: dict[str, Any] = json.loads((answered or b"{}").split(b"\n")[0])
    return parsed


def process_info_reply(*, socket_path: str, pane_id: str) -> dict[str, Any]:
    """The WHOLE `pane.process_info` reply, envelope included.

    Deliberately not the unwrapped `result.process_info`: the envelope is where
    an unusable answer is visible, and unwrapping it in the caller is what made
    a missing field raise rather than refuse.
    """
    return raw_request(
        socket_path=socket_path,
        method="pane.process_info",
        params={"pane_id": pane_id},
    )


# --------------------------------------------------------- the write-side gate


@dataclass(kw_only=True)
class ReadyShellGate:
    """The real writer, plus a one-shot establishment of the created pane's shell.

    Forwards every request to `inner` verbatim and rewrites nothing. Its only
    effect is that the FIRST `pane.process_info` for a pane is preceded by the
    establishment step: optionally a real transient startup process, OBSERVED
    running and then observed gone, and then a bounded wait for that pane to
    report an idle retained shell.

    The transient is what makes this exercise independent of the operator's
    personal shell configuration. On the host, a freshly created pane's `zsh`
    forks `mise` and `atuin` during startup, so the adapter's pre-launch reading
    legitimately finds the pane OCCUPIED and refuses the launch — a correct
    refusal that the positive exercises used to report as a failed layout.

    **What the injected transient is, stated exactly, because the weaker claim
    is the honest one.** It stages a BOUNDED DISCRIMINATING INSTANCE of a
    non-idle created pane: one real, distinctly named, self-terminating child,
    observed and then cleared. It is NOT a reproduction of the operator's
    `zsh`/`mise`/`atuin` startup, and no exercise here should be read as having
    reproduced that host failure. What it discriminates is the fixture premise —
    whether readiness was ESTABLISHED or merely inherited from a login shell
    that loads nothing — which is the premise the repair is about.
    """

    inner: Any
    socket_path: str
    startup_transient: str = ""
    transient_name: str = ""
    seconds: float = READY_TIMEOUT
    methods: list[str] = field(default_factory=list)
    gated: list[str] = field(default_factory=list)
    transient: ChildObservation | None = None
    established: ShellRecovery | None = None

    def request(
        self, *, target: Any, method: str, params: Mapping[str, object], expect: Any
    ) -> Any:
        pane_id = str(params.get("pane_id", ""))
        if method == "pane.process_info" and pane_id not in self.gated:
            self.gated.append(pane_id)
            self._establish(pane_id=pane_id)
        self.methods.append(method)
        return self.inner.request(target=target, method=method, params=params, expect=expect)

    def place_above(self, *, target: Any, cwd: str, command: str, ratio: float) -> Any:
        """The REAL layout sequence, with this gate as its bounded requester.

        The proof is taken from `inner`'s OWN fields rather than rebuilt here,
        so the exercise runs against the kernel readers and the host shell
        register the shipped writer would use.
        """
        layout = importlib.import_module("herdr_layout")
        shell_identity = importlib.import_module("_herdr_shell_identity")
        return layout.place_above(
            requester=self,
            target=target,
            cwd=cwd,
            command=command,
            proof=shell_identity.ShellProof(
                evidence_of=self.inner.shell_evidence_of,
                login_shells=self.inner.login_shells,
                shell_aliases=self.inner.shell_aliases,
            ),
            ratio=ratio,
        )

    def refusal(self) -> str:
        """Why this gate did NOT establish its precondition, or ``""``.

        A real setup failure must be explicit: an exercise that asserts on the
        adapter without checking this would grade a fixture timeout as product
        behaviour, which is the defect this whole file exists to retire.
        """
        if not self.gated:
            return "the adapter never read a pane's process info, so nothing was established"
        if self.startup_transient and (self.transient is None or self.transient.pid is None):
            observed = "" if self.transient is None else self.transient.reason
            return f"the controlled startup transient was never observed: {observed}"
        if self.established is None or not self.established.recovered:
            return "" if self.established is None else self.established.reason
        return ""

    def _establish(self, *, pane_id: str) -> None:
        def read() -> Mapping[str, Any]:
            return process_info_reply(socket_path=self.socket_path, pane_id=pane_id)

        if self.startup_transient:
            _ = raw_request(
                socket_path=self.socket_path,
                method="pane.send_input",
                params={
                    "pane_id": pane_id,
                    "text": self.startup_transient,
                    "keys": ["Enter"],
                },
            )
            self.transient = await_occupying_child(
                read=read, name=self.transient_name, poll=BoundedPoll(seconds=self.seconds)
            )
        self.established = await_idle_shell(
            read=read, pane_id=pane_id, poll=BoundedPoll(seconds=self.seconds)
        )


# ------------------------------------------------------------------- controls
#
# Deterministic controls over scripted readings. Each one is a defect this file
# replaces, reproduced with the numbers it was measured with, so a regression in
# any helper fails here rather than in a native exercise where it would read as
# an adapter failure.

PANE = "w1:p3"
HOST_SHELL_PID = 3584980
HOST_TRANSIENT_PID = 3585294
HOST_SLEEP_PID = 3585400


def _reading(
    *, group_id: int, processes: tuple[tuple[int, str], ...], shell_pid: int = HOST_SHELL_PID
) -> dict[str, Any]:
    return {
        "result": {
            "process_info": {
                "pane_id": PANE,
                "shell_pid": shell_pid,
                "foreground_process_group_id": group_id,
                "foreground_processes": [
                    {"pid": pid, "name": name, "cmdline": name, "cwd": "/tmp"}
                    for pid, name in processes
                ],
            }
        }
    }


def _frozen_poll(*, seconds: float, ticks: list[float]) -> BoundedPoll:
    """A poll whose clock advances only through `ticks`, and never really sleeps.

    **Every caller needs at least THREE ticks, and the reason is a property of
    this harness rather than of anything it tests.** The waits read the clock
    once to compute their deadline and again on each `while` test, so a
    two-element `[0.0, 2.0]` against `seconds=1.0` expires on the FIRST test and
    the loop body never runs — the wait then reports "no process reading was
    taken before the deadline", which is true and is not the refusal the control
    meant to assert. An intermediate tick (`[0.0, 0.5, 2.0]`) buys exactly one
    reading before expiry, which is what a timeout control wants: a real refusal
    first, then the bound.

    **Two controls were authored with two ticks and failed on first run. That was
    a defect in THIS function's callers, not in any helper, and it is recorded so
    nobody re-reads it as one.** Nothing in `await_occupying_child`,
    `await_idle_shell` or `_recovery_refusal` changed to make them pass, and no
    assertion in either control was weakened — the fix was the inserted tick and
    nothing else. It is not a Red-Green pair over a product or helper defect, and
    it is not evidence about either.
    """
    remaining = list(ticks)

    def monotonic() -> float:
        return remaining.pop(0) if remaining else 1e9

    return BoundedPoll(seconds=seconds, monotonic=monotonic, sleep=lambda _seconds: None)


def test_the_requested_child_under_the_retained_shell_is_established() -> None:
    """The positive control, so every refusal below cannot pass by refusing all."""
    reading = read_foreground(
        reply=_reading(
            group_id=HOST_SLEEP_PID,
            processes=((HOST_SLEEP_PID, "sleep"),),
        )
    )

    assert reading is not None
    observed = occupying_child_pid(
        reading=reading,
        name="sleep",
        parent_of=lambda pid: HOST_SHELL_PID if pid == HOST_SLEEP_PID else None,
        group_of=lambda pid: HOST_SLEEP_PID if pid == HOST_SLEEP_PID else None,
    )

    assert observed.pid == HOST_SLEEP_PID, observed.reason
    assert observed.reason == ""


def test_a_transient_startup_process_is_not_the_requested_occupying_child() -> None:
    """THE measured defect: `mv` from shell startup is not an observed `sleep`.

    The numbers are the ones read off the operator host — shell `zsh` 3584980,
    foreground 3585294 named `mv` — because this exact reading is what the old
    "any group differing from the shell" wait accepted as proof that a live
    child occupied the pane.
    """
    reading = read_foreground(
        reply=_reading(
            group_id=HOST_TRANSIENT_PID,
            processes=((HOST_TRANSIENT_PID, "mv"),),
        )
    )

    assert reading is not None
    assert reading.is_idle() is False, "the pane's foreground really had left its shell"
    observed = occupying_child_pid(
        reading=reading,
        name="sleep",
        parent_of=lambda pid: HOST_SHELL_PID if pid == HOST_TRANSIENT_PID else None,
        group_of=lambda pid: HOST_TRANSIENT_PID if pid == HOST_TRANSIENT_PID else None,
    )

    assert observed.pid is None, "a startup transient was accepted as the requested child"
    assert "'sleep'" in observed.reason, observed.reason
    assert "mv" in observed.reason, observed.reason


def test_a_child_that_is_not_the_shell_s_own_is_refused() -> None:
    """A foreground `sleep` whose parent is not the pane's shell proves nothing."""
    reading = read_foreground(
        reply=_reading(group_id=HOST_SLEEP_PID, processes=((HOST_SLEEP_PID, "sleep"),))
    )

    assert reading is not None
    observed = occupying_child_pid(
        reading=reading,
        name="sleep",
        parent_of=lambda pid: 1 if pid == HOST_SLEEP_PID else None,
        group_of=lambda pid: HOST_SLEEP_PID if pid == HOST_SLEEP_PID else None,
    )

    assert observed.pid is None
    assert "not the retained shell" in observed.reason, observed.reason


def test_a_child_outside_the_panes_foreground_group_is_refused() -> None:
    """Being LISTED beside the foreground is not being the foreground."""
    reading = read_foreground(
        reply=_reading(group_id=HOST_TRANSIENT_PID, processes=((HOST_SLEEP_PID, "sleep"),))
    )

    assert reading is not None
    observed = occupying_child_pid(
        reading=reading,
        name="sleep",
        parent_of=lambda pid: HOST_SHELL_PID if pid == HOST_SLEEP_PID else None,
        group_of=lambda pid: HOST_SLEEP_PID if pid == HOST_SLEEP_PID else None,
    )

    assert observed.pid is None
    assert "foreground group" in observed.reason, observed.reason


def test_a_reading_missing_the_foreground_group_is_an_unsuccessful_observation() -> None:
    """The measured `KeyError` is now a refusal with a reason, raised at nobody.

    Driven through `await_occupying_child` rather than only through
    `read_foreground`, because the exception was raised inside the setup loop
    and that is the surface a caller actually uses.
    """
    assert read_foreground(reply={"result": {"process_info": {"shell_pid": 1}}}) is None
    assert read_foreground(reply={"error": {"code": "no_such_pane"}}) is None

    observed = await_occupying_child(
        read=lambda: {"result": {"process_info": {"pane_id": PANE, "shell_pid": HOST_SHELL_PID}}},
        name="sleep",
        poll=_frozen_poll(seconds=1.0, ticks=[0.0, 0.5, 2.0]),
    )

    assert observed.pid is None
    assert "no usable shell/foreground fields" in observed.reason, observed.reason


def test_a_setup_timeout_is_reported_rather_than_returned_silently() -> None:
    """An expired setup deadline must never read as an established precondition."""
    observed = await_occupying_child(
        read=lambda: _reading(group_id=HOST_SHELL_PID, processes=((HOST_SHELL_PID, "zsh"),)),
        name="sleep",
        poll=_frozen_poll(seconds=1.0, ticks=[0.0, 0.5, 2.0]),
    )

    assert observed.pid is None
    assert "was observed within 1.0s" in observed.reason, observed.reason
    assert "is still its shell" in observed.reason, observed.reason


def test_idle_recovery_is_waited_for_rather_than_inferred_from_a_child_exit() -> None:
    """The measured lifecycle defect: the child was gone and the shell was not back.

    The first reading is the one taken on the host immediately after the child
    disappeared — two `zsh` children still listed and a foreground group that is
    not the shell. Recovery is the SECOND reading, and it has to be waited for.
    """
    readings = [
        _reading(
            group_id=HOST_TRANSIENT_PID,
            processes=((HOST_TRANSIENT_PID, "zsh"), (HOST_TRANSIENT_PID + 1, "zsh")),
        ),
        _reading(group_id=HOST_SHELL_PID, processes=((HOST_SHELL_PID, "zsh"),)),
    ]

    recovery = await_idle_shell(
        read=lambda: readings.pop(0) if len(readings) > 1 else readings[0],
        pane_id=PANE,
        poll=_frozen_poll(seconds=5.0, ticks=[0.0, 0.1, 0.2]),
        expected=ShellIdentityPin(pid=HOST_SHELL_PID, starttime=164433575),
        starttime_of_pid=lambda pid: 164433575 if pid == HOST_SHELL_PID else None,
    )

    assert recovery.recovered is True, recovery.reason
    assert readings == [_reading(group_id=HOST_SHELL_PID, processes=((HOST_SHELL_PID, "zsh"),))]


def test_a_shell_that_never_regains_its_foreground_is_an_explicit_failure() -> None:
    """An unrecovered shell is reported, not waited out and then asserted around."""
    recovery = await_idle_shell(
        read=lambda: _reading(
            group_id=HOST_TRANSIENT_PID, processes=((HOST_TRANSIENT_PID, "zsh"),)
        ),
        pane_id=PANE,
        poll=_frozen_poll(seconds=2.0, ticks=[0.0, 1.0, 3.0]),
        expected=ShellIdentityPin(pid=HOST_SHELL_PID, starttime=164433575),
        starttime_of_pid=lambda pid: 164433575 if pid == HOST_SHELL_PID else None,
    )

    assert recovery.recovered is False
    assert "never reported an idle retained shell within 2.0s" in recovery.reason, recovery.reason


def test_a_recycled_shell_pid_is_not_the_same_retained_shell() -> None:
    """Same pid, different start time: a DIFFERENT process now holds that number."""
    recovery = await_idle_shell(
        read=lambda: _reading(group_id=HOST_SHELL_PID, processes=((HOST_SHELL_PID, "zsh"),)),
        pane_id=PANE,
        poll=_frozen_poll(seconds=1.0, ticks=[0.0, 0.5, 2.0]),
        expected=ShellIdentityPin(pid=HOST_SHELL_PID, starttime=164433575),
        starttime_of_pid=lambda pid: 999999999 if pid == HOST_SHELL_PID else None,
    )

    assert recovery.recovered is False
    assert "no longer carries start time" in recovery.reason, recovery.reason


def test_a_reading_about_another_pane_establishes_nothing() -> None:
    """A reply describing a different pane is not evidence about this one."""
    recovery = await_idle_shell(
        read=lambda: _reading(group_id=HOST_SHELL_PID, processes=((HOST_SHELL_PID, "zsh"),)),
        pane_id="w1:p9",
        poll=_frozen_poll(seconds=1.0, ticks=[0.0, 0.5, 2.0]),
    )

    assert recovery.recovered is False
    assert "not 'w1:p9'" in recovery.reason, recovery.reason


# --------------------------------------- the transient's portability control
#
# The control over the FIFTH measured defect, the one this section was added
# for: a transient whose name came from COPYING `sleep` under a new name did
# not run at all on the operator host, because that host's `sleep` is a
# MULTICALL executable which decides WHICH utility to be from the name it was
# invoked under.
#
# The executable staged below is a small `sh` script this file writes. It is
# NOT uutils coreutils, and the control below is a DISCLOSED MECHANISM control
# rather than a reproduction: what it stages is the one mechanism the host
# failure turns on — dispatch on the invocation name — so that a transient
# depending on a rename cannot run under it. The real uutils boundary is a HOST
# assertion and nothing here stands in for it.

# The refusal a multicall executable answers a name it does not know with,
# quoted from the measured host receipt below.
MULTICALL_REFUSAL = "function/utility not found"
_REAL_SLEEP_TOKEN = "@REAL_SLEEP@"
_MULTICALL_SOURCE = """\
#!/bin/sh
# A stand-in for a MULTICALL coreutils executable, written by
# tests/test_herdr_live_observations.py. The utility it runs is the NAME it was
# invoked under; an unrecognized name falls back to the FIRST ARGUMENT, which is
# how `coreutils sleep 2` dispatches. Under its own name it is a real `sleep`.
#
# The name is taken by parameter expansion rather than by `basename`, and the
# real sleep is reached by absolute path: this control repoints PATH at the
# directory it stages, so a stub needing anything FROM PATH would fail for a
# reason that has nothing to do with its invocation name.
utility=${0##*/}
if [ "$utility" != sleep ]; then
    utility="$1"
    shift
fi
if [ "$utility" != sleep ]; then
    echo "$utility: function/utility not found"
    exit 1
fi
exec "@REAL_SLEEP@" "$@"
"""


def _multicall_sleep(*, directory: Path) -> Path:
    """A real, invocation-name-sensitive `sleep` executable in `directory`.

    It dispatches to the host's genuine `sleep` under its own name, so a refusal
    from a COPY of it is about the name it was invoked under and not about a
    control that never worked.
    """
    real = shutil.which("sleep")
    assert real is not None, "this control dispatches to the host's own real sleep"
    staged = directory / "sleep"
    _ = staged.write_text(_MULTICALL_SOURCE.replace(_REAL_SLEEP_TOKEN, real), encoding="utf-8")
    staged.chmod(0o755)
    return staged


def _ran(*, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """One bounded foreground run of this control's own staged executable."""
    return subprocess.run(  # noqa: S603 — an executable this control just wrote
        argv, capture_output=True, text=True, timeout=READY_TIMEOUT, check=False
    )


def _named_processes_under(*, shell: int, name: str) -> tuple[int, ...]:
    """Every process named `name` that IS `shell` or is one of its children.

    Both shapes are accepted because both are honest: `sh -c` may `exec` a
    single command in place rather than forking it, so the process carrying the
    name is sometimes the shell's own pid. The lineage bound is what keeps a
    same-named process from another test out of the answer.
    """
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if comm == name and (pid == shell or parent_pid_of(pid=pid) == shell):
            found.append(pid)
    return tuple(found)


@dataclass(frozen=True, kw_only=True)
class _TransientRun:
    """One real run of a staged transient command, as OBSERVED from `/proc`."""

    observed: tuple[int, ...]
    starttime: int | None
    status: int | None
    output: str
    elapsed: float


def _run_transient(*, command: str) -> _TransientRun:
    """Run `command` in a real shell and observe the named child it produces."""
    started = time.monotonic()
    shell = subprocess.Popen(  # noqa: S603 — /bin/sh running this fixture's own command
        ["/bin/sh", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    observed: tuple[int, ...] = ()
    deadline = started + READY_TIMEOUT
    while time.monotonic() < deadline and not observed:
        finished = shell.poll() is not None
        observed = _named_processes_under(shell=shell.pid, name=TRANSIENT_NAME)
        if observed:
            break
        # A shell that has already exited will not go on to produce the child,
        # so waiting out the rest of the bound would only make a real refusal
        # slow. `finished` is sampled BEFORE the reading so the two cannot
        # disagree about a child that started and exited between them.
        if finished:
            break
        time.sleep(POLL_SECONDS)
    starttime = None if not observed else starttime_of(pid=observed[0])
    output = shell.communicate(timeout=READY_TIMEOUT)[0]
    return _TransientRun(
        observed=observed,
        starttime=starttime,
        status=shell.returncode,
        output=output,
        elapsed=time.monotonic() - started,
    )


def test_the_staged_executable_dispatches_on_the_name_it_was_invoked_under(
    *, tmp_path: Path
) -> None:
    """The control's own mechanism, proven BOTH ways before anything leans on it.

    Under the name `sleep` it really sleeps and exits 0; copied to
    :data:`TRANSIENT_NAME` it refuses with the message the operator host printed,
    naming the ARGUMENT it fell back to. Without this leg the refusal below could
    equally be a broken stand-in.
    """
    multicall = _multicall_sleep(directory=tmp_path)

    worked = _ran(argv=[str(multicall), "0"])
    assert worked.returncode == 0, worked
    renamed = tmp_path / TRANSIENT_NAME
    _ = shutil.copy(multicall, renamed)
    refused = _ran(argv=[str(renamed), str(TRANSIENT_SECONDS)])

    assert refused.returncode != 0, "a copy under a foreign name must refuse, not sleep"
    assert MULTICALL_REFUSAL in refused.stdout, refused
    assert str(TRANSIENT_SECONDS) in refused.stdout, refused


def test_the_startup_transient_runs_where_sleep_dispatches_on_its_invocation_name(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The transient's identity and lifetime must not depend on a renamed utility.

    **The measured host receipt this control exists for** (work-item
    `overseer-emzwpx`). On the operator host `/usr/bin/sleep` resolves to
    `/usr/lib/cargo/bin/coreutils/sleep` — uutils coreutils 0.2.2, 10832184
    bytes, sha256
    `2a9b9ccf4e9724a6d6d8c97c835c9932223fbdefc9706fef9d0dfef7a9076739`. A copy of
    it named `ovstartup`, run with the argument `0`, exited 1 in 0.2 seconds
    printing `0: function/utility not found` and never slept. So every exercise
    that staged a transient refused its own fixture premise:
    `tests/test_herdr_live_layout.py::test_the_requested_command_runs_in_the_new_pane_s_retained_shell`
    failed twice with "controlled ovstartup was not observed within 30 seconds".
    The pinned factory sandbox has a GNU STANDALONE `sleep` (35336 bytes,
    sha256 `8ac215ec4c1ce4a9c23a10cd3e5898d60419bdfab1ac7444d6bdd1690701de24`),
    which is why the native exercises passed here throughout and why the real
    uutils boundary stays a HOST assertion this control does not discharge.

    What is asserted here is the PORTABILITY property, with `sleep` on this
    process's PATH replaced by the disclosed invocation-name-sensitive executable
    the leg above proved both ways: the command the fixture hands a pane must
    still produce ONE real process carrying the requested name, alive when
    observed, for its whole declared lifetime, exiting on its own with nothing
    written to its terminal.
    """
    staged = tmp_path / "bin"
    staged.mkdir()
    multicall = _multicall_sleep(directory=staged)
    monkeypatch.setenv("PATH", str(staged))
    assert shutil.which("sleep") == str(multicall), "this control owns what `sleep` resolves to"

    run = _run_transient(command=startup_transient(scratch=tmp_path))

    assert len(run.observed) == 1, (
        f"no single process named {TRANSIENT_NAME!r} ran under the staged transient: observed "
        f"{run.observed}, shell exited {run.status} with output {run.output!r}"
    )
    assert run.starttime is not None, f"{TRANSIENT_NAME} {run.observed[0]} was gone when observed"
    assert run.status == 0, f"the transient exited {run.status} with output {run.output!r}"
    assert run.output == "", f"the transient wrote to its terminal: {run.output!r}"
    assert run.elapsed >= TRANSIENT_SECONDS, (
        f"the transient was finished after {run.elapsed:.2f}s, short of its declared "
        f"{TRANSIENT_SECONDS}s lifetime"
    )
    assert starttime_of(pid=run.observed[0]) != run.starttime, (
        f"{TRANSIENT_NAME} {run.observed[0]} still carries start time {run.starttime}, so it "
        "never exited"
    )
