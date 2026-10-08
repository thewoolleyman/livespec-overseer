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
pid; `await_child_gone` answers the OTHER half of that same chronology — whether
the child really left — about an identity rather than a pid number, and only on
POSITIVE evidence. That last qualifier is the fifth defect of this kind, found in
owner source review of this very file: `/proc` readers here answer None for every
failure alike, so "no start time" was read as "the process exited" and an
UNREADABLE `/proc` entry produced a clean observed-exit. Absence and
unavailability are now separate states (`ProcReading`), and only the kernel
denying a pid is evidence an exit happened. Nothing here sleeps to wait out a
race — each loop polls a real reading under a bound it reports when it expires.

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
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import herdr_identity
import herdr_protocol
import herdr_transport
import herdr_write
import pytest

__all__: list[str] = [
    "BoundedPoll",
    "ChildExit",
    "ChildObservation",
    "ForegroundReading",
    "OwnedServer",
    "PaneIdentity",
    "PaneReadiness",
    "ProcReading",
    "ReadyShellGate",
    "ReadyWriter",
    "RegisteredShell",
    "ShellIdentityPin",
    "ShellRecovery",
    "await_child_gone",
    "await_coherent_identity",
    "await_idle_shell",
    "await_occupying_child",
    "child_environment",
    "child_umask",
    "herdr_cli",
    "kernel_executable_of",
    "leader_name",
    "minimal_registered_shell",
    "occupying_child_pid",
    "owned_config",
    "owned_environment",
    "pane_capture",
    "pane_identity_of",
    "pane_ids",
    "parent_pid_of",
    "process_group_of",
    "process_info_reply",
    "raw_request",
    "read_foreground",
    "registered_login_shells",
    "require_herdr",
    "run_in_pane",
    "session_socket",
    "split_pane",
    "start_owned_server",
    "starttime_of",
    "startup_transient",
    "stop_owned_server",
]

POLL_SECONDS = 0.1
READY_TIMEOUT = 30.0
PidReader = Callable[..., int | None]
# A reader of ONE pane's whole `pane.process_info` reply. Injectable so a control
# can drive an unavailable or contradictory reading without manufacturing one on a
# real server, which is the only way some of them can be staged at all.
PaneReader = Callable[..., Mapping[str, Any]]
ExecutableReader = Callable[..., str | None]

# ------------------------------------------- the owned native server's own setup
#
# Every native exercise in this family used to start its herdr server with the
# AMBIENT environment and no configuration of its own, so which shell its panes
# came up in — and which startup files that shell ran — were the operator's
# choices rather than the fixture's. Both are now DECLARED here and asserted
# below; see `start_owned_server` and `owned_environment` for the mechanism and
# `test_the_owned_server_runs_its_declared_minimal_shell_despite_an_inherited_config`
# for the receipts.

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
PANE_CWD = "/tmp"
# The host's OWN login-shell register — the same authority the adapter's
# retained-shell proof consults, which is why a declared shell has to appear in it.
LOGIN_SHELL_REGISTRY = "/etc/shells"
# Candidate MINIMAL shells, in preference order. A minimal shell is the point:
# the fewer startup hooks a pane's shell has, the less of the exercise depends on
# host configuration. Each candidate still has to be available AND registered.
MINIMAL_SHELL_CANDIDATES = ("/usr/bin/dash", "/bin/dash")
# Herdr's documented startup mode for a new interactive pane shell. `non_login`
# is the narrower of the two real modes and is deliberately not `auto`.
OWNED_SHELL_MODE = "non_login"
# The ONLY variables removed from the launched server's copied child environment.
# `$ENV` is a POSIX shell's INTERACTIVE startup file, which `non_login` does not
# disable — see `owned_environment` for the measurement.
EXCLUDED_CHILD_VARIABLES = ("ENV",)


@dataclass(frozen=True, kw_only=True)
class RegisteredShell:
    """One login-shell register entry, as DECLARED beside what it resolves to.

    The declared form is kept because the NAME is load-bearing: a pane reporting
    `sh` is reconciled with a kernel executable of `/usr/bin/dash` by the name the
    host registers, and that name is unanswerable once the path has been resolved
    away.
    """

    declared: str
    name: str
    resolved: str


@dataclass(frozen=True, kw_only=True)
class OwnedServer:
    """One owned herdr server child, its socket, its root pane and its OWN setup.

    `config_path` and `declared_shell` are carried because they are what makes
    this server's panes independent of the ambient environment, and an exercise
    has to be able to assert them rather than trust them.
    """

    session: str
    socket_path: str
    server_pid: int
    config_path: str
    declared_shell: str
    root: str


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


@dataclass(frozen=True, kw_only=True)
class ProcReading:
    """`/proc/<pid>/stat` as THREE outcomes, because two of them cannot be honest.

    `fields` is populated only when the file was actually read. `absent` is True
    for ENOENT/ESRCH alone — the kernel saying this pid does not exist, which is
    the ONLY `/proc` failure that is EVIDENCE a process left. Every other
    `OSError` (EACCES, EPERM, EIO) sets `error` and leaves both of the others
    empty: the evidence is UNAVAILABLE, which is evidence of neither presence nor
    absence.

    **The three-way split exists because collapsing it to two was a real defect
    in this file.** `_stat_fields` answers None for every failure, so a caller
    reading "no start time" as "the process exited" grades a `/proc` read it was
    not allowed to make as an OBSERVED NATURAL EXIT. That is the opposite of what
    the native exercises require of themselves — an unavailable reading is a
    FIXTURE FAILURE naming what it could not see, never an establishment — and it
    was shipped here with a control that asserted the wrong half: the control
    supplied a reader which would have reported the child ALIVE and asserted
    success without ever consulting it.
    """

    fields: tuple[str, ...]
    absent: bool
    error: str


def _stat_reading(*, pid: int) -> ProcReading:
    """`pid`'s post-comm `/proc/<pid>/stat` fields, or WHICH kind of nothing.

    The comm field can contain spaces and parentheses, so the fields after it
    are taken from the LAST close parenthesis rather than by splitting the whole
    line.

    `FileNotFoundError` and `ProcessLookupError` are separated from the rest
    DELIBERATELY and are the whole point of this function: they are the kernel
    reporting that no such pid exists, and nothing else about a `/proc` read is.
    """
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError):
        return ProcReading(fields=(), absent=True, error="")
    except OSError as failed:
        return ProcReading(
            fields=(), absent=False, error=f"/proc/{pid}/stat could not be read: {failed}"
        )
    return ProcReading(fields=tuple(stat[stat.rindex(")") + 1 :].split()), absent=False, error="")


def _stat_fields(*, pid: int) -> list[str] | None:
    """`pid`'s post-comm stat fields, or None when they could not be read at all.

    Deliberately KEEPS collapsing absence and unavailability into None, because
    None is all its three callers can act on: `parent_pid_of`, `process_group_of`
    and `starttime_of` answer "what is this value", and both failures mean there
    is no value to answer with. Each of them is used to QUALIFY an observation,
    so a None correctly fails that observation closed.

    The distinction those three cannot carry is the subject of
    :func:`await_child_gone`, which asks the opposite question — "has this process
    LEFT?" — where absence is a positive answer and unavailability is not. That
    one reads :func:`_stat_reading` directly and must never be routed through
    here.
    """
    reading = _stat_reading(pid=pid)
    return None if reading.absent or reading.error else list(reading.fields)


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


@dataclass(frozen=True, kw_only=True)
class ChildExit:
    """Whether `pid` is PROVABLY gone, and why that is unproven when it is not.

    `gone` is True only on positive evidence — the kernel denying the pid, or the
    pid carrying a DIFFERENT process than the one observed. `reason` is non-empty
    for both of the other two states, which a caller must treat alike: a child
    still present has not exited YET, and a reading that could not be taken says
    nothing about whether it has.
    """

    gone: bool
    reason: str


ExitReader = Callable[..., ProcReading]


def _child_exit(*, pid: int, starttime: int, read: ExitReader) -> ChildExit:
    """One reading's answer to "has the process observed as `starttime` left?".

    Four readings, three answers, and the fourth is the one that used to be
    missing:

      - the kernel denies the pid — GONE, which is the ordinary ending;
      - the pid exists carrying a DIFFERENT start time, so the number was
        recycled and the process observed under `starttime` has left — GONE;
      - the pid exists carrying the SAME start time — present, not gone;
      - the read FAILED for any other reason — UNAVAILABLE, reported as its own
        refusal rather than folded into either of the first two.
    """
    reading = read(pid=pid)
    if reading.absent:
        return ChildExit(gone=True, reason="")
    if reading.error:
        return ChildExit(gone=False, reason=reading.error)
    if int(reading.fields[19]) != starttime:
        return ChildExit(gone=True, reason="")
    return ChildExit(
        gone=False, reason=f"child {pid} is still present carrying start time {starttime}"
    )


def await_child_gone(
    *,
    pid: int,
    starttime: int | None,
    poll: BoundedPoll,
    read: ExitReader = _stat_reading,
) -> str:
    """``""`` once `pid` is PROVABLY gone, or why its exit was not established.

    Nothing here signals the child: an ORDINARY exit is the whole point, because
    a pane whose process is killed is not the same observation as a pane whose
    bounded child finished. The comparison is against the start time the caller
    OBSERVED the child with, so the answer is about an IDENTITY rather than about
    a pid number.

    **A `starttime` of None is a REFUSAL, and reading it as an exit was a defect
    shipped in this function's first cut.** The argument then made was that the
    observation it came from had found the pid alive, so a missing start time
    could only mean the child had since exited. That is wrong, and `_stat_fields`
    is why: it answers None for EVERY `/proc` failure, not only for a pid the
    kernel denies. So an unreadable `/proc` entry — any reason at all — arrived
    here as None and was graded as an observed natural exit, which is both the
    opposite of the "unavailable readiness is a fixture failure" rule the native
    exercises are held to, and a claim about a process this function never saw
    leave. Unavailability is now reported, at entry and on every later reading.
    """
    if starttime is None:
        return (
            f"child {pid}'s own start time was never readable, so its exit cannot be "
            "observed at all; an unavailable identity is not an observed exit"
        )
    deadline = poll.monotonic() + poll.seconds
    reason = "no /proc reading was taken before the deadline"
    while poll.monotonic() < deadline:
        exited = _child_exit(pid=pid, starttime=starttime, read=read)
        if exited.gone:
            return ""
        reason = exited.reason
        poll.sleep(POLL_SECONDS)
    return f"child {pid} was not observed gone within {poll.seconds}s: {reason}"


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


def pane_capture(*, socket_path: str, pane_id: str) -> str:
    """`pane_id`'s visible text, read from the REAL server over a raw socket."""
    reply = raw_request(
        socket_path=socket_path,
        method="pane.read",
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def pane_ids(*, socket_path: str) -> list[str]:
    """Every pane the server currently holds, so a closure or survival is a fact."""
    reply = raw_request(socket_path=socket_path, method="pane.list", params={})
    return [str(pane["pane_id"]) for pane in reply["result"]["panes"]]


def split_pane(
    *, socket_path: str, pane_id: str, direction: str, ratio: float = 0.5, cwd: str = PANE_CWD
) -> str:
    """Split `pane_id` directly on the real server, for SETUP and for controls.

    A raw split is how a control observes a pane whose creation this fixture owns
    end to end — the one case where the exact created pane is knowable without
    going through the adapter at all.
    """
    reply = raw_request(
        socket_path=socket_path,
        method="pane.split",
        params={
            "target_pane_id": pane_id,
            "direction": direction,
            "ratio": ratio,
            "cwd": cwd,
            "focus": False,
        },
    )
    assert "result" in reply, f"setup split of {pane_id!r} failed: {reply}"
    return str(reply["result"]["pane"]["pane_id"])


def run_in_pane(*, socket_path: str, pane_id: str, command: str) -> None:
    """Deliver `command` plus Enter to `pane_id` on the REAL server, as SETUP.

    Fixture input goes straight to the real socket so it never enters whatever
    request stream an exercise is counting the WRITER's own deliveries in.
    """
    _ = raw_request(
        socket_path=socket_path,
        method="pane.send_input",
        params={"pane_id": pane_id, "text": command, "keys": ["Enter"]},
    )


def kernel_executable_of(*, pid: int) -> str | None:
    """`pid`'s resolved `/proc/<pid>/exe`, or None when the KERNEL half is unavailable.

    `readlink` rather than a realpath of the magic link: resolving the PATH of a
    process that is GONE answers `/proc/<pid>/exe` unchanged, which would
    manufacture an executable for a dead pid. The target is then resolved so a host
    where `/bin/bash` symlinks to `/usr/bin/bash` compares equal either way.

    This is the FIXTURE's own instrument, deliberately not the adapter's reader: an
    exercise taking its premise from the surface under test would only prove that
    surface self-consistent.
    """
    try:
        target = Path(f"/proc/{pid}/exe").readlink()
    except OSError:
        return None
    return str(target.resolve())


def child_environment(*, pid: int) -> dict[str, str]:
    """`pid`'s own environment, read from `/proc` — what the child ACTUALLY got.

    Read from the kernel rather than from the mapping this process handed
    `Popen`, so "the parent environment was preserved" is a claim about the
    launched process rather than about the fixture's intent.
    """
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    return dict(
        entry.split("=", 1)
        for entry in raw.decode("utf-8", errors="replace").split("\0")
        if "=" in entry
    )


def child_umask(*, pid: int) -> str:
    """`pid`'s umask as the kernel reports it, or ``""`` when `/proc` omits it."""
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("Umask:"):
            return line.split(":", 1)[1].strip()
    return ""


# ------------------------------------------------------ the owned native server


def require_herdr() -> None:
    """Skip the calling exercise when this host has no herdr to drive."""
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")


def herdr_cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    """One bounded run of the herdr CLI, for session setup and teardown only."""
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def registered_login_shells() -> tuple[RegisteredShell, ...]:
    """Every login shell this host's own register declares, under its declared name.

    The register is READ rather than enumerated, and an empty answer is not
    special-cased: it means this host registers nothing, which is a fact the
    caller has to act on rather than a condition to paper over.
    """
    try:
        raw = Path(LOGIN_SHELL_REGISTRY).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return tuple(
        RegisteredShell(declared=entry, name=Path(entry).name, resolved=os.path.realpath(entry))
        for entry in (line.strip() for line in raw.splitlines())
        if entry and not entry.startswith("#")
    )


def minimal_registered_shell() -> RegisteredShell | None:
    """The first AVAILABLE and REGISTERED minimal shell, or None when there is none.

    Both halves are required and neither is assumed. "Available" is an executable
    file the kernel can actually run; "registered" is an entry in this host's own
    login-shell register, which is the same authority the adapter's retained-shell
    proof consults. A fixture that declared an unregistered executable would be
    manufacturing a shell the product is entitled to refuse.
    """
    registered = {entry.resolved for entry in registered_login_shells()}
    for candidate in MINIMAL_SHELL_CANDIDATES:
        resolved = os.path.realpath(candidate)
        if resolved in registered and os.access(resolved, os.X_OK):
            return RegisteredShell(declared=candidate, name=Path(resolved).name, resolved=resolved)
    return None


def owned_config(*, scratch: Path, default_shell: str, shell_mode: str = OWNED_SHELL_MODE) -> Path:
    """A PRIVATE herdr config selecting `default_shell`, written under `scratch`.

    Herdr 0.9.3 documents `HERDR_CONFIG_PATH` as selecting the config file a
    process reads, and `[terminal] default_shell` / `shell_mode` as the executable
    and startup mode of every new interactive pane. An EMPTY `default_shell` is
    herdr's documented "use `$SHELL`, then `/bin/sh`" selection, which is the
    mechanism the alias exercises vary — so this helper EXPRESSES a shell rather
    than imposing one, and passing `""` leaves that selection exactly as it was.

    This is controlled TEST setup. It is never a statement about how a real
    operator's panes are bootstrapped, and it must never be read as one.
    """
    scratch.mkdir(parents=True, exist_ok=True)
    path = scratch / "herdr-config.toml"
    _ = path.write_text(
        "# Written by tests/test_herdr_live_observations.py for ONE owned server.\n"
        "[terminal]\n"
        f'default_shell = "{default_shell}"\n'
        f'shell_mode = "{shell_mode}"\n',
        encoding="utf-8",
    )
    return path


def owned_environment(*, config_path: Path) -> dict[str, str]:
    """The PARENT environment, with exactly two deliberate differences.

    `HERDR_CONFIG_PATH` is repointed at this fixture's own private config, which
    is what makes an inherited one — the operator's, or a rival fixture's —
    inert for the launched server. And the variables in
    :data:`EXCLUDED_CHILD_VARIABLES` are REMOVED from the copy.

    **Why `ENV` is excluded even though the config already says `non_login`.**
    `shell_mode = "non_login"` governs whether the pane's shell reads its LOGIN
    profile. It does not disable `$ENV`, which a POSIX shell reads for every
    INTERACTIVE invocation — measured in this sandbox 2026-10-07 with
    `shell_mode = "non_login"` and `ENV` pointing at a file echoing a marker,
    every freshly created pane's capture carried that marker. So the one
    remaining startup hook is removed from the CHILD's copy of the environment.

    Everything else is preserved verbatim and deliberately: `HOME`, `CODEX_HOME`,
    `PATH`, and — because this is a copy rather than a scrub — every other
    inherited value. The child's umask is inherited too, because nothing here
    calls `os.umask`. The PARENT's own environment is never mutated: this returns
    a new mapping.
    """
    environment = dict(os.environ)
    environment["HERDR_CONFIG_PATH"] = str(config_path)
    for name in EXCLUDED_CHILD_VARIABLES:
        _ = environment.pop(name, None)
    return environment


def stop_owned_server(*, session: str) -> None:
    """Stop and delete EXACTLY `session`, touching no other herdr session.

    **An absent binary means there is nothing of ours to stop, and saying so is
    not a swallowed error.** :func:`start_owned_server` calls
    :func:`require_herdr` before it spawns anything, so a session can only exist
    if the binary was reachable; when it is not, no owned server was ever created
    and this cleanup has no work. Returning here is therefore the ACCURATE answer
    for that one condition, not a tolerance for failure: nothing is caught, and a
    reachable binary that then refuses, times out, or exits non-zero is left to
    behave exactly as it did before.

    Why the distinction is load-bearing. Every caller runs this from a `finally`
    guarding a `try` that may have raised `Skipped` out of `require_herdr`. Since
    `herdr_cli` execs the binary by name, an unreachable one raised
    `FileNotFoundError` from inside that `finally` and REPLACED the in-flight
    skip, so a host simply lacking the capability reported errors instead of
    skips — thirteen of them on CI run 37722427716 (nine at setup, four at
    teardown), each chained as "During handling of the above exception, another
    exception occurred". See
    `tests/test_herdr_live_retained_shell_launch.py::test_an_absent_herdr_lets_this_fixtures_setup_skip_reach_the_runner`.
    """
    if shutil.which(HERDR_BINARY) is None:
        return
    _ = herdr_cli(args=["--session", session, "server", "stop"])
    _ = herdr_cli(args=["session", "delete", session])


def session_socket(*, session: str) -> Path:
    """Where herdr puts `session`'s API socket."""
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def start_owned_server(
    *,
    session: str,
    scratch: Path,
    log_name: str = "server.log",
    default_shell: str | None = None,
    cwd: str = PANE_CWD,
) -> OwnedServer:
    """One owned herdr server whose panes run a DECLARED shell, plus its root pane.

    `default_shell` of None means :func:`minimal_registered_shell` — the shared
    family's declared minimal shell — and the exercise SKIPS when this host
    registers none, rather than silently falling back to whatever the ambient
    environment would have produced. Passing an explicit path declares that
    shell; passing `""` leaves herdr's own `$SHELL`-then-`/bin/sh` selection in
    force, which is what an alias exercise needs.

    **Server creation and the initial setup are enclosed in cleanup.** The socket
    wait and the `workspace.create` are both fallible, and a failure in either
    used to leave a live server child and a registered session behind. Anything
    raised past the spawn now stops and deletes EXACTLY this session — its own
    resource, named explicitly — and re-raises.
    """
    require_herdr()
    declared = default_shell
    if declared is None:
        minimal = minimal_registered_shell()
        if minimal is None:
            pytest.skip(
                f"{LOGIN_SHELL_REGISTRY} registers none of {list(MINIMAL_SHELL_CANDIDATES)}, so "
                "this host cannot declare a minimal shell for an owned server"
            )
        declared = minimal.declared
    config = owned_config(scratch=scratch / f"{session}-config", default_shell=declared)
    log = (scratch / log_name).open("wb")
    child = subprocess.Popen(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, "--session", session, "server"],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(scratch),
        env=owned_environment(config_path=config),
    )
    try:
        address = session_socket(session=session)
        deadline = time.monotonic() + SERVER_READY_TIMEOUT
        while time.monotonic() < deadline and not address.exists():
            time.sleep(POLL_SECONDS)
        log.close()
        assert address.exists(), (
            f"herdr session {session!r} never created {address}; "
            f"server log: {(scratch / log_name).read_text(errors='replace')[:500]}"
        )
        created = raw_request(
            socket_path=str(address),
            method="workspace.create",
            params={"cwd": cwd, "label": session, "focus": False},
        )
        assert "result" in created, f"workspace.create failed: {created}"
    except BaseException:
        log.close()
        stop_owned_server(session=session)
        raise
    return OwnedServer(
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        config_path=str(config),
        declared_shell=declared,
        root=str(created["result"]["root_pane"]["pane_id"]),
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

    **"Observed gone" and "the SAME shell" are both measurements now, and neither
    was before.** The establishment used to observe the child and then wait for
    the pane to report ANY idle shell: the child's exit was inferred from the
    foreground group returning to a shell, and the shell was whichever one the
    pane happened to report at that moment. So it pins the child's `/proc` parent
    — the retained shell the observation already proved the child hung off — as an
    IDENTITY (pid AND start time), waits for the child itself to leave `/proc`
    under that same identity discipline, and only then waits for THAT shell to own
    its foreground again. Both halves are reported through :meth:`refusal`, so an
    expired wait is a named fixture failure rather than an establishment.

    **An UNAVAILABLE reading fails every one of those closed, in both halves.** A
    child whose own `/proc` identity cannot be read is not a child observed
    exiting, and a shell whose identity cannot be pinned is not a shell this gate
    may say recovered — so `refusal()` names each of those cases separately
    instead of treating a missing reading as a satisfied step. See
    :func:`await_child_gone` for the defect that rule is written against.

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
    retained: ShellIdentityPin | None = None
    departed: str | None = None
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

        **A SEPARATE DETERMINISTIC FINDING, disclosed on its own terms: an
        `established` of None used to answer ``""``.** The predecessor read
        `if self.established is None or not self.established.recovered: return ""
        if self.established is None else self.established.reason`, so a gate whose
        `_establish` had RAISED — leaving `gated` holding the pane and `established`
        unset — reported NO refusal at all. Every consumer that wraps the
        establishment in its own `try` therefore had to assign `established` by hand
        for the failure to be visible, and one that forgot would grade its exercise
        on a precondition nothing established. The missing-establishment branch is
        now named, and it names the pane.

        **This is NOT the cause of the four observed native failures** recorded in
        work-item `overseer-3zfpz5`. Three were a created pane whose foreground
        differed from its retained shell at the adapter's own reading, and the fourth
        was an unusable native process reading at a raw split — all four reached an
        observation the predecessor DID report. The control for this branch is
        `test_an_initially_unavailable_exact_pane_setup_is_a_named_fixture_refusal`,
        and no measured consequence is claimed for it beyond what that control shows.
        """
        if not self.gated:
            return "the adapter never read a pane's process info, so nothing was established"
        staged = self._transient_refusal()
        if staged:
            return staged
        if self.established is None:
            return (
                f"the establishment for {self.gated[0]!r} never completed its idle-shell "
                "observation, so nothing about that pane is established"
            )
        if not self.established.recovered:
            return self.established.reason
        return ""

    def _transient_refusal(self) -> str:
        """Why the STAGED transient half of the establishment failed, or ``""``.

        Split out of :meth:`refusal` by cohesion rather than by line count: these
        three answers are all about the controlled child this gate staged — observed,
        pinned to a retained shell, and seen to exit — while the two that remain are
        about the pane's own idle-shell observation. An establishment configured with
        no transient has nothing to answer here and says so by returning ``""``.
        """
        if not self.startup_transient:
            return ""
        if self.transient is None or self.transient.pid is None:
            observed = "" if self.transient is None else self.transient.reason
            return f"the controlled startup transient was never observed: {observed}"
        if self.retained is None:
            return (
                f"the controlled startup transient's retained shell could not be pinned as an "
                f"identity, so {self.gated[0]!r} readiness cannot be established"
            )
        if self.departed:
            return f"the controlled startup transient never exited: {self.departed}"
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
            self._clear_transient(child=self.transient.pid)
        self.established = await_idle_shell(
            read=read,
            pane_id=pane_id,
            poll=BoundedPoll(seconds=self.seconds),
            expected=self.retained,
        )

    def _clear_transient(self, *, child: int | None) -> None:
        """Pin the child's own retained shell, then wait for the child to exit.

        The shell comes from the child's `/proc` parent rather than from a fresh
        reading, because `occupying_child_pid` has already PROVEN that parent is
        the pane's `shell_pid` — re-reading it would only introduce a second
        answer that could disagree.
        """
        if child is None:
            return
        shell = parent_pid_of(pid=child)
        shell_starttime = None if shell is None else starttime_of(pid=shell)
        if shell is not None and shell_starttime is not None:
            self.retained = ShellIdentityPin(pid=shell, starttime=shell_starttime)
        self.departed = await_child_gone(
            pid=child, starttime=starttime_of(pid=child), poll=BoundedPoll(seconds=self.seconds)
        )


# ------------------------------- the exact created pane's COHERENT identity
#
# `ReadyShellGate` establishes that a pane is AVAILABLE — its shell owns an idle
# foreground, observed through a real transient and a real recovery. That is only
# half of what an exercise needs before it may grade the adapter's retained-shell
# proof, and the missing half produced a measured host failure of its own: the
# created pane `w1:p2` reported its shell as `'herdr'` while the kernel ran
# `/usr/bin/bash`, and the product REFUSED — correctly, because one of two
# truthful-looking sources must be wrong. The fixture had never observed the two
# descriptions to agree about the pane it was about to grade.
#
# So readiness here is two observations, not one: AVAILABLE (the gate) and
# COHERENT (this section). Both are bounded, both report their own expiry, and
# neither is ever inferred from the other.


def leader_name(*, reading: ForegroundReading) -> str:
    """The name the server gives the entry that OWNS the foreground group, or ``""``.

    Empty when the reply names no single leader, which is an unusable reading rather
    than an approximation — the same discrimination the adapter's own reader makes.
    """
    named = [name for pid, name in reading.processes if pid == reading.group_id]
    return named[0] if len(named) == 1 else ""


@dataclass(frozen=True, kw_only=True)
class PaneIdentity:
    """ONE pane's server-reported shell name against the KERNEL's executable for it.

    The facts are carried even on a refusal, because they are what a fixture failure
    has to NAME: which pane, which shell pid, what the server called it, and what the
    kernel runs. `mediated_by` is the login-shell register entry that reconciled the
    two, and is empty when the basenames already agreed.
    """

    pane_id: str
    shell_pid: int
    reported: str
    executable: str
    mediated_by: str
    coherent: bool
    reason: str


def _no_identity(*, pane_id: str, reason: str) -> PaneIdentity:
    """An observation that established nothing, carrying only why."""
    return PaneIdentity(
        pane_id=pane_id,
        shell_pid=0,
        reported="",
        executable="",
        mediated_by="",
        coherent=False,
        reason=reason,
    )


def pane_identity_of(
    *,
    reading: ForegroundReading,
    pane_id: str,
    registered: tuple[RegisteredShell, ...],
    executable_of: ExecutableReader = kernel_executable_of,
) -> PaneIdentity:
    """Whether `reading` shows ONE program answering to two truthful descriptions.

    Four conditions, all required, because the question is only meaningful about an
    idle shell this pane actually owns:

      1. the reading is about `pane_id` and not about some other pane;
      2. the pane's own retained shell owns its foreground group, so the leader the
         server names IS that shell rather than a child of it;
      3. the kernel answers for that pid at all — an unreadable `/proc/<pid>/exe` is
         UNAVAILABLE evidence, never agreement;
      4. the two descriptions agree: equal basenames, or a name this host REGISTERS
         for exactly the executable the kernel reports. Matching the name alone would
         reinstate the single-source trust the agreement rule exists to prevent.
    """
    if reading.pane_id != pane_id:
        return _no_identity(
            pane_id=pane_id,
            reason=f"the reading describes pane {reading.pane_id!r}, not {pane_id!r}",
        )
    if not reading.is_idle():
        return _no_identity(
            pane_id=pane_id,
            reason=(
                f"{pane_id!r} is OCCUPIED: foreground group {reading.group_id} is not its "
                f"retained shell {reading.shell_pid}, so its leader is not the shell"
            ),
        )
    reported = leader_name(reading=reading)
    if not reported:
        return _no_identity(
            pane_id=pane_id,
            reason=f"the reply names no single foreground group leader: {list(reading.processes)}",
        )
    executable = executable_of(pid=reading.shell_pid)
    if executable is None:
        return _no_identity(
            pane_id=pane_id,
            reason=(
                f"/proc/{reading.shell_pid}/exe could not be read, so the KERNEL half of "
                f"{pane_id!r}'s shell identity is unavailable"
            ),
        )
    mediating = [
        entry.declared
        for entry in registered
        if entry.name == reported and entry.resolved == executable
    ]
    agreed = Path(executable).name == reported
    return PaneIdentity(
        pane_id=pane_id,
        shell_pid=reading.shell_pid,
        reported=reported,
        executable=executable,
        mediated_by="" if agreed or not mediating else mediating[0],
        coherent=agreed or bool(mediating),
        reason=(
            ""
            if agreed or mediating
            else (
                f"herdr calls {pane_id!r}'s shell {reading.shell_pid} {reported!r} while the "
                f"kernel runs {executable!r}, and no registered login shell mediates them"
            )
        ),
    )


def await_coherent_identity(
    *,
    read: PaneReader,
    pane_id: str,
    poll: BoundedPoll,
    registered: tuple[RegisteredShell, ...],
    executable_of: ExecutableReader = kernel_executable_of,
) -> PaneIdentity:
    """Poll real readings until `pane_id`'s two shell descriptions agree, or say why not.

    **A one-shot unusable reading is CONSUMED and retried, not accepted and not
    fatal.** That is the whole reason this is a bounded wait rather than a single
    read: the measured fourth native failure of this family was a raw-split pane
    whose FIRST process reading carried no usable fields at all, taken with no wait
    behind it. A reading that cannot be used establishes nothing and is also no
    evidence that the pane is unsound — so the loop takes another one.

    The expiry is REPORTED, carrying the last thing seen. A wait that fell out of its
    bound silently is exactly how a fixture comes to grade the adapter on a premise it
    never established.
    """
    deadline = poll.monotonic() + poll.seconds
    verdict = _no_identity(
        pane_id=pane_id, reason="no process reading was taken before the deadline"
    )
    while poll.monotonic() < deadline:
        reading = read_foreground(reply=read())
        if reading is None:
            verdict = _no_identity(
                pane_id=pane_id,
                reason="the herdr process reading carried no usable shell/foreground fields",
            )
        else:
            verdict = pane_identity_of(
                reading=reading,
                pane_id=pane_id,
                registered=registered,
                executable_of=executable_of,
            )
            if verdict.coherent:
                return verdict
        poll.sleep(POLL_SECONDS)
    return replace(
        verdict,
        reason=(
            f"{pane_id!r} never reported a coherent shell identity within {poll.seconds}s: "
            f"{verdict.reason}"
        ),
    )


@dataclass(frozen=True, kw_only=True)
class _SetupRequests:
    """A `BoundedRequests`-shaped forwarder to the REAL server, for SETUP only.

    `ReadyShellGate` establishes a pane's readiness around a request it then forwards
    to whatever it wraps. Here what it wraps is this: a raw round trip taken on the
    FIXTURE's own behalf. So the gate's reading is unmistakably a setup observation —
    it is not a request the writer made, and it is recorded in neither
    :meth:`PaneReadiness.methods` nor :meth:`PaneReadiness.deliveries`.

    `target` and `expect` are the protocol's peer-validation and
    envelope-expectation arguments, which only a real writer acts on; this forwarder
    ignores both, and its reply is consumed by the gate and discarded.
    """

    socket_path: str

    def request(
        self, *, target: Any, method: str, params: Mapping[str, object], expect: Any
    ) -> dict[str, Any]:
        return raw_request(socket_path=self.socket_path, method=method, params=dict(params))


@dataclass(kw_only=True)
class PaneReadiness:
    """The EXACT created pane's AVAILABLE and COHERENT identity, established once.

    Two independent observations, in this order, both about the pane the adapter just
    created and neither taken from the adapter:

      1. the delivered :class:`ReadyShellGate` — one real bounded child staged in that
         pane, OBSERVED running under the pane's own retained shell, that shell pinned
         as an IDENTITY (pid AND start time), the child observed exiting on its OWN,
         and the same identity observed owning its foreground again;
      2. :func:`await_coherent_identity` — the pane's server-reported shell name and
         the kernel's executable for that shell observed to describe ONE program, by
         basename or by this host's own login-shell register.

    `registered` is the FIXTURE's own reading of the host register, used only for the
    premise in (2). It is never handed to the adapter, whose own `shell_aliases` is
    what the exercises grade.

    `requests` is the WRITER's own request stream, recorded at the seam
    :class:`ReadyWriter` interposes. The gate's traffic never enters it: the staged
    child and the gate's own reading both go to the real socket on raw connections,
    so a zero-delivery claim describes the surface under test alone.

    `occupy_after` / `occupant` are the LATE fixture step — an occupant introduced
    AFTER initial readiness, at a named point in the writer's own sequence. It is
    deliberately not part of the establishment: the establishment is one-shot, so the
    reading that meets a late occupant is the writer's RECHECK, with no establishment
    and no waiting behind it. That is what keeps the fixture from waiting the occupant
    away.
    """

    socket_path: str
    transient: str
    registered: tuple[RegisteredShell, ...] = field(default_factory=registered_login_shells)
    seconds: float = READY_TIMEOUT
    coherence_seconds: float = READY_TIMEOUT
    read: PaneReader | None = None
    occupy_after: str = ""
    occupant: Callable[..., ChildObservation] | None = None
    # Real, OWNED unavailability, for the controls: the fixture closes the pane it is
    # about to establish, so the server genuinely has no reading to give for it.
    # Never set by an exercise.
    close_before_establishing: bool = False
    panes: list[str] = field(default_factory=list)
    gate: ReadyShellGate | None = None
    identity: PaneIdentity | None = None
    occupation: ChildObservation | None = None
    requests: list[dict[str, Any]] = field(default_factory=list)

    def methods(self) -> list[str]:
        return [str(request["method"]) for request in self.requests]

    def deliveries(self) -> list[tuple[str, str, tuple[str, ...]]]:
        """Every `(pane, text, keys)` the WRITER delivered — this fixture's setup excluded.

        The keys are carried because the launch is ONE atomic text-plus-Enter call, so
        an empty list is the byte-level statement that neither the command nor its
        submission reached any pane.
        """
        return [
            (
                str(request["params"].get("pane_id")),
                str(request["params"].get("text")),
                tuple(str(key) for key in request["params"].get("keys", [])),
            )
            for request in self.requests
            if request["method"] == herdr_protocol.METHOD_PANE_SEND_INPUT
        ]

    def record(self, *, method: str, params: Mapping[str, object]) -> None:
        self.requests.append({"method": method, "params": dict(params)})

    def _read_for(self, *, pane_id: str) -> PaneReader:
        if self.read is not None:
            return self.read
        return lambda: process_info_reply(socket_path=self.socket_path, pane_id=pane_id)

    def establish(self, *, pane_id: str) -> None:
        """Establish both observations for `pane_id`, REPORTING rather than raising.

        A raise here would surface as whatever the writer's next request happened to
        do, which is how a fixture comes to grade an establishment it never made.
        Every failure is recorded and answered by :meth:`refusal`.
        """
        self.panes.append(pane_id)
        gate = ReadyShellGate(
            inner=_SetupRequests(socket_path=self.socket_path),
            socket_path=self.socket_path,
            startup_transient=self.transient,
            transient_name=TRANSIENT_NAME,
            seconds=self.seconds,
        )
        self.gate = gate
        try:
            if self.close_before_establishing:
                _ = raw_request(
                    socket_path=self.socket_path,
                    method="pane.close",
                    params={"pane_id": pane_id},
                )
            _ = gate.request(
                target=None,
                method=herdr_protocol.METHOD_PANE_PROCESS_INFO,
                params={"pane_id": pane_id},
                expect=None,
            )
            self.identity = await_coherent_identity(
                read=self._read_for(pane_id=pane_id),
                pane_id=pane_id,
                poll=BoundedPoll(seconds=self.coherence_seconds),
                registered=self.registered,
            )
        except OSError as failed:
            gate.established = ShellRecovery(
                recovered=False, reason=f"the readiness step failed: {failed}"
            )

    def stage_occupant(self) -> None:
        """Run the LATE fixture step against the established pane, reporting failures.

        One-shot, and only after an establishment has named a pane: an occupant staged
        before there is a pane to stage it in would be a different exercise.
        """
        if self.occupant is None or not self.panes or self.occupation is not None:
            return
        try:
            self.occupation = self.occupant(pane_id=self.panes[0])
        except OSError as failed:
            self.occupation = ChildObservation(
                pid=None, reason=f"the late occupation step failed: {failed}"
            )

    def refusal(self) -> str:
        """Why this fixture did NOT establish the created pane's readiness, or ``""``."""
        if self.gate is None:
            return "the readiness step never ran, so nothing about the created pane is established"
        if self.gate.refusal():
            return self.gate.refusal()
        if self.identity is None:
            return "the created pane's server/kernel shell identity was never observed at all"
        return self.identity.reason


@dataclass(frozen=True, kw_only=True)
class ReadyWriter(herdr_write.HerdrWriter):
    """The SHIPPED writer, with the created pane's readiness established mid-sequence.

    `split_window_top` is INHERITED verbatim — this class adds no facade, and callers
    assert that identity rather than trusting it. So the sequence, the proofs, the
    `ShellProof` built from this writer's own fields, the socket, the per-request
    deadline and the peer revalidation are all the shipped facade's. Reaching
    `herdr_layout.place_above` directly instead would enter one layer BELOW the
    surface these exercises are about.

    The one interposition is at `request`, which is PUBLIC precisely because
    `herdr_layout` runs its whole sequence on it. Before the FIRST
    `pane.process_info` naming a pane, and only the first, the readiness
    establishment runs; then the writer's own request goes through unchanged. After
    the request named by `PaneReadiness.occupy_after` returns, the late fixture step
    runs — which is how an occupant arrives AFTER initial readiness and before the
    writer's own recheck.

    **The establishment costs no request its deadline**, because it completes before
    `super().request` hands anything to `herdr_transport`.

    All mutable state lives on the `PaneReadiness`: this writer is frozen because the
    shipped one is, and a frozen dataclass cannot record anything on itself.
    """

    readiness: PaneReadiness

    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome:
        pane_id = str(params.get("pane_id", ""))
        self.readiness.record(method=method, params=params)
        first_reading = (
            method == herdr_protocol.METHOD_PANE_PROCESS_INFO
            and bool(pane_id)
            and pane_id not in self.readiness.panes
        )
        if first_reading:
            self.readiness.establish(pane_id=pane_id)
        outcome = super().request(target=target, method=method, params=params, expect=expect)
        if method and method == self.readiness.occupy_after:
            self.readiness.stage_occupant()
        return outcome


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


HOST_CHILD_STARTTIME = 164433575


def _present(*, starttime: int) -> ProcReading:
    """A `/proc/<pid>/stat` that WAS read, carrying `starttime` in field 22."""
    fields = ["0"] * 20
    fields[19] = str(starttime)
    return ProcReading(fields=tuple(fields), absent=False, error="")


_ABSENT = ProcReading(fields=(), absent=True, error="")
_UNREADABLE = ProcReading(fields=(), absent=False, error="/proc/x/stat could not be read: EACCES")


def test_a_child_the_kernel_denies_is_observed_gone() -> None:
    """The positive control: ENOENT is the one `/proc` failure that proves an exit."""
    readings = [_present(starttime=HOST_CHILD_STARTTIME), _ABSENT]

    departed = await_child_gone(
        pid=HOST_SLEEP_PID,
        starttime=HOST_CHILD_STARTTIME,
        poll=_frozen_poll(seconds=5.0, ticks=[0.0, 0.1, 0.2]),
        read=lambda pid: readings.pop(0) if readings else _ABSENT,
    )

    assert departed == "", departed
    assert readings == [], "the wait must have taken BOTH readings, not stopped at the first"


def test_a_child_still_carrying_its_start_time_is_reported_rather_than_waited_out() -> None:
    """An expired exit wait must name what it saw, never read as an ordinary exit."""
    departed = await_child_gone(
        pid=HOST_SLEEP_PID,
        starttime=HOST_CHILD_STARTTIME,
        poll=_frozen_poll(seconds=2.0, ticks=[0.0, 1.0, 3.0]),
        read=lambda pid: _present(starttime=HOST_CHILD_STARTTIME),
    )

    assert "was not observed gone within 2.0s" in departed, departed
    assert "still present carrying start time" in departed, departed
    assert str(HOST_SLEEP_PID) in departed, departed


def test_a_recycled_pid_holding_another_process_counts_as_gone() -> None:
    """Same number, different start time: the child this exercise watched has left."""
    departed = await_child_gone(
        pid=HOST_SLEEP_PID,
        starttime=HOST_CHILD_STARTTIME,
        poll=_frozen_poll(seconds=1.0, ticks=[0.0, 0.5, 2.0]),
        read=lambda pid: _present(starttime=999999999),
    )

    assert departed == "", departed


def test_an_unreadable_proc_entry_is_never_graded_as_an_observed_exit() -> None:
    """THE owner-found defect, as its own control: unavailable is not absent.

    A `/proc` read that failed for any reason OTHER than the kernel denying the
    pid is evidence of neither presence nor absence. The predecessor routed every
    failure through `_stat_fields`, which answers None for all of them, and then
    read None as "different from the observed start time" — so an unreadable entry
    returned a clean exit observation. It must refuse, and the refusal must carry
    the read error so the fixture failure names what it could not see.

    Driven through the whole wait rather than through one reading, because the
    defect applies to EVERY later reading and not only to the first.
    """
    departed = await_child_gone(
        pid=HOST_SLEEP_PID,
        starttime=HOST_CHILD_STARTTIME,
        poll=_frozen_poll(seconds=2.0, ticks=[0.0, 0.5, 1.0, 3.0]),
        read=lambda pid: _UNREADABLE,
    )

    assert departed != "", "an unreadable /proc entry was graded as an observed exit"
    assert "could not be read" in departed, departed
    assert "was not observed gone within 2.0s" in departed, departed


def test_an_unreadable_reading_midway_does_not_end_the_wait_early() -> None:
    """Present, then unavailable, then absent: only the LAST one is an exit.

    The sequence is the one a real exercise can meet — a `/proc` read that fails
    transiently while the child is still running — and the control's value is that
    the middle reading must be CONSUMED and rejected rather than returned on.
    """
    readings = [_present(starttime=HOST_CHILD_STARTTIME), _UNREADABLE, _ABSENT]

    departed = await_child_gone(
        pid=HOST_SLEEP_PID,
        starttime=HOST_CHILD_STARTTIME,
        poll=_frozen_poll(seconds=5.0, ticks=[0.0, 0.1, 0.2, 0.3]),
        read=lambda pid: readings.pop(0) if readings else _ABSENT,
    )

    assert departed == "", departed
    assert readings == [], "the unavailable middle reading must not have ended the wait"


def test_a_child_whose_start_time_was_never_read_is_not_an_observed_exit() -> None:
    """An unavailable INITIAL identity is a fixture failure, not an exit.

    This control asserted the exact opposite when it was written — it supplied a
    reader that would have reported the child ALIVE and asserted SUCCESS without
    consulting it, which is how the defect reached a green suite. The reader is
    kept, and the assertion that nothing consulted it is kept, because that fact
    is now the POINT: with no identity to compare against there is nothing a
    reading could settle, so the only honest answer is to refuse.
    """
    consulted: list[int] = []

    def read(*, pid: int) -> ProcReading:
        consulted.append(pid)
        return _present(starttime=HOST_CHILD_STARTTIME)

    departed = await_child_gone(
        pid=HOST_SLEEP_PID,
        starttime=None,
        poll=_frozen_poll(seconds=1.0, ticks=[0.0, 0.5, 2.0]),
        read=read,
    )

    assert "an unavailable identity is not an observed exit" in departed, departed
    assert str(HOST_SLEEP_PID) in departed, departed
    assert consulted == [], "there is no identity to compare, so nothing may be read"


def test_the_proc_reader_maps_a_kernel_denied_pid_to_absence_against_the_real_proc() -> None:
    """The reader's own ENOENT mapping, read from the REAL `/proc`.

    The denied pid is one past `/proc/sys/kernel/pid_max`, so the kernel can never
    have allocated it and the ENOENT is guaranteed by construction rather than by
    winning a race against a child being reaped. That is deliberately the WEAKER,
    exact claim: what this pins is the reader's MAPPING from a denied pid to
    `absent` with no error — the one `/proc` state the exit observation is allowed
    to act on — not that any particular process was watched leaving. Real leaving
    is observed elsewhere in this file, by the native exercises that run a bounded
    child and then see its start time stop being carried.

    The control is bounded two ways on purpose. A LIVE pid must read as present
    with real fields, so it cannot pass by answering absent to everything. And the
    other half — a `/proc` entry that exists and cannot be READ — is driven through
    the injected seam in the controls above rather than staged here: this sandbox
    runs as root, so no `/proc` entry it can see is unreadable, and manufacturing
    one would be a different mechanism wearing the same name. The split is
    disclosed rather than papered over.

    It spawns nothing. An earlier cut reaped a real `sys.executable` child, which
    `check-tests-no-subprocess-spawn` correctly rejected; routing that same spawn
    through `/bin/sh` to get past the matcher would have been evasion, and
    allowlisting this path would have weakened a shared check for one control's
    convenience.
    """
    pid_max = int(Path("/proc/sys/kernel/pid_max").read_text(encoding="utf-8").strip())

    denied = _stat_reading(pid=pid_max + 1)
    live = _stat_reading(pid=os.getpid())

    assert denied.absent is True, f"a pid the kernel cannot own must read as ENOENT: {denied}"
    assert denied.error == "", f"absence must not be reported as a read failure: {denied}"
    assert live.absent is False and live.error == "", live
    assert int(live.fields[19]) == starttime_of(
        pid=os.getpid()
    ), "the reading and the delivered start-time reader must agree on this process"


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


# ------------------------- the exact created pane's INITIAL setup, as a premise
#
# The two controls below are the accepted behavioural regression for work-item
# `overseer-3zfpz5`. Each drives the DELIVERED, pre-change helper in this file and
# fails on what that helper does, not on a symbol it lacks.


def test_an_initially_unavailable_exact_pane_setup_is_a_named_fixture_refusal(
    *, tmp_path: Path
) -> None:
    """An establishment that could not be TAKEN at all must refuse, naming the pane.

    Every consumer of this gate wraps the establishment in its own `try`, because
    `_establish` talks to a real socket and a real socket can be gone. So the
    question this control asks is the one those consumers depend on the answer to:
    after an establishment that raised, does the gate REPORT that nothing about the
    pane was established?

    The unavailability is real and owned — the socket path names a file this
    exercise never created, so the very first `pane.process_info` for the exact
    pane raises — and the gate is driven in its DEFAULT configuration, with no
    staged transient, which is the configuration whose establishment is a single
    bounded idle-shell observation and nothing else.

    `gated` already holds the pane, so the gate knows exactly which pane it failed
    to establish; a refusal that does not name it leaves a consumer unable to say
    which pane its exercise is unsound about.
    """
    missing = tmp_path / "no-such-herdr.sock"

    gate = ReadyShellGate(inner=None, socket_path=str(missing))
    with pytest.raises(FileNotFoundError, match="No such file or directory"):
        _ = gate.request(
            target=None, method="pane.process_info", params={"pane_id": PANE}, expect=None
        )

    assert gate.gated == [PANE], gate.gated
    assert gate.transient is None, "this configuration stages no transient at all"
    assert gate.established is None, "the idle-shell observation never completed"
    assert gate.refusal() != "", (
        "an establishment that could not be taken at all reported NO refusal, so a consumer "
        "catching that error grades its exercise on a precondition nothing established"
    )
    assert PANE in gate.refusal(), gate.refusal()


# ------------------- the exact created pane's COHERENT identity, as controls
#
# Deterministic controls over scripted readings, plus one native control at an
# OWNED fixture boundary. The host receipt each deterministic control is built from
# is named in its docstring, so a regression fails here rather than in a native
# exercise where it would read as an adapter failure.

# The measured host receipt from work-item `overseer-3kojxx`: the created pane
# `w1:p2` reported its shell as `'herdr'` while the kernel ran `/usr/bin/bash`.
HOST_INCOHERENT_PANE = "w1:p2"
HOST_INCOHERENT_NAME = "herdr"
HOST_INCOHERENT_EXECUTABLE = "/usr/bin/bash"
# The Debian-family mediation this family's alias case turns on: `/bin/sh` is
# declared, reports `sh`, and resolves to `/usr/bin/dash`.
_DEBIAN_SH = RegisteredShell(declared="/bin/sh", name="sh", resolved="/usr/bin/dash")


def _identity_reading(
    *, pane_id: str, name: str, shell_pid: int = HOST_SHELL_PID
) -> dict[str, Any]:
    """An IDLE reading for `pane_id` whose foreground leader is its own shell."""
    return {
        "result": {
            "process_info": {
                "pane_id": pane_id,
                "shell_pid": shell_pid,
                "foreground_process_group_id": shell_pid,
                "foreground_processes": [
                    {"pid": shell_pid, "name": name, "cmdline": name, "cwd": "/tmp"}
                ],
            }
        }
    }


def test_a_pane_whose_two_shell_descriptions_agree_by_basename_is_coherent() -> None:
    """The positive control, so every refusal below cannot pass by refusing all.

    The declared minimal shell this family's owned servers run is exactly this
    shape: herdr reports `dash` and the kernel runs `/usr/bin/dash`, so the two
    agree without any register entry having to mediate them.
    """
    reading = read_foreground(reply=_identity_reading(pane_id=PANE, name="dash"))

    assert reading is not None
    identity = pane_identity_of(
        reading=reading,
        pane_id=PANE,
        registered=(),
        executable_of=lambda pid: "/usr/bin/dash" if pid == HOST_SHELL_PID else None,
    )

    assert identity.coherent is True, identity.reason
    assert identity.mediated_by == "", "agreement by basename needs no register entry"
    assert identity.shell_pid == HOST_SHELL_PID
    assert identity.reason == ""


def test_a_registered_name_mediates_two_descriptions_that_do_not_match_by_basename() -> None:
    """The alias case the family must keep supporting: `sh` running `/usr/bin/dash`.

    Both sources are truthful — `sh` is what the shell was INVOKED as, `dash` is
    what the kernel RESOLVED it to — and the host's own register is what reconciles
    them. The entry that did so is NAMED, so an exercise can assert it reached the
    alias path rather than a pane that happened to agree.
    """
    reading = read_foreground(reply=_identity_reading(pane_id=PANE, name="sh"))

    assert reading is not None
    identity = pane_identity_of(
        reading=reading,
        pane_id=PANE,
        registered=(_DEBIAN_SH,),
        executable_of=lambda pid: _DEBIAN_SH.resolved if pid == HOST_SHELL_PID else None,
    )

    assert identity.coherent is True, identity.reason
    assert identity.mediated_by == _DEBIAN_SH.declared, identity
    assert Path(identity.executable).name != identity.reported, identity


def test_a_contradictory_exact_pane_identity_is_a_bounded_fixture_refusal() -> None:
    """THE measured host receipt: `'herdr'` against `/usr/bin/bash`, nothing mediating.

    This is the reading the product refused and the fixture had never looked at. An
    unmediated disagreement must expire the bound and NAME all four facts — the
    pane, the shell pid, what the server called it, what the kernel runs — because a
    refusal that names none of them leaves a reader unable to tell a contradictory
    pane from an unavailable one.
    """
    identity = await_coherent_identity(
        read=lambda: _identity_reading(pane_id=HOST_INCOHERENT_PANE, name=HOST_INCOHERENT_NAME),
        pane_id=HOST_INCOHERENT_PANE,
        poll=_frozen_poll(seconds=2.0, ticks=[0.0, 1.0, 3.0]),
        registered=(_DEBIAN_SH,),
        executable_of=lambda pid: HOST_INCOHERENT_EXECUTABLE,
    )

    assert identity.coherent is False
    assert (
        "never reported a coherent shell identity within 2.0s" in identity.reason
    ), identity.reason
    assert repr(HOST_INCOHERENT_NAME) in identity.reason, identity.reason
    assert repr(HOST_INCOHERENT_EXECUTABLE) in identity.reason, identity.reason
    assert str(HOST_SHELL_PID) in identity.reason, identity.reason
    assert HOST_INCOHERENT_PANE in identity.reason, identity.reason


def test_a_one_shot_unusable_first_reading_is_followed_by_real_coherent_evidence() -> None:
    """A DISCLOSED one-shot fault at the initial setup seam, then real evidence.

    The fault is this control's own: the first reply carries no usable shell or
    foreground fields at all, which is the shape of the measured fourth native
    failure — a raw-split pane read immediately, with no wait behind it. It is NOT a
    reconstruction of that failure's timing, and nothing here claims to reproduce
    when or why the host produced it.

    What is asserted is the property the wait owes: an unusable reading establishes
    nothing AND condemns nothing, so it is consumed and another is taken. Both
    replies must be used — a wait that returned on the first would never see the
    second, and a wait that refused on the first would turn a transient into a
    fixture failure.
    """
    replies = [
        {"result": {"process_info": {"pane_id": PANE, "shell_pid": HOST_SHELL_PID}}},
        _identity_reading(pane_id=PANE, name="dash"),
    ]

    identity = await_coherent_identity(
        read=lambda: replies.pop(0) if replies else _identity_reading(pane_id=PANE, name="dash"),
        pane_id=PANE,
        poll=_frozen_poll(seconds=5.0, ticks=[0.0, 0.1, 0.2]),
        registered=(),
        executable_of=lambda pid: "/usr/bin/dash",
    )

    assert identity.coherent is True, identity.reason
    assert replies == [], "the unusable first reading must have been consumed, not returned on"


def test_a_persistently_unavailable_reading_is_a_bounded_fixture_refusal() -> None:
    """An unusable reading that never becomes usable is a NAMED expiry, not a pass."""
    identity = await_coherent_identity(
        read=lambda: {"error": {"code": "no_such_pane"}},
        pane_id=PANE,
        poll=_frozen_poll(seconds=2.0, ticks=[0.0, 1.0, 3.0]),
        registered=(),
    )

    assert identity.coherent is False
    assert "no usable shell/foreground fields" in identity.reason, identity.reason
    assert f"{PANE!r} never reported a coherent shell identity" in identity.reason, identity.reason


def test_an_occupied_pane_cannot_testify_about_its_own_shell_identity() -> None:
    """A pane whose foreground is a CHILD names a child, not the shell.

    So coherence is only asked of an idle pane, and an occupied one is reported as
    occupied rather than graded on whatever its foreground leader happens to be
    called.
    """
    reading = read_foreground(
        reply=_reading(group_id=HOST_SLEEP_PID, processes=((HOST_SLEEP_PID, "sleep"),))
    )

    assert reading is not None
    identity = pane_identity_of(reading=reading, pane_id=PANE, registered=())

    assert identity.coherent is False
    assert "is OCCUPIED" in identity.reason, identity.reason


def test_an_unreadable_kernel_half_is_unavailable_evidence_rather_than_agreement() -> None:
    """A `/proc/<pid>/exe` that cannot be read is not two sources agreeing."""
    reading = read_foreground(reply=_identity_reading(pane_id=PANE, name="dash"))

    assert reading is not None
    identity = pane_identity_of(
        reading=reading, pane_id=PANE, registered=(), executable_of=lambda pid: None
    )

    assert identity.coherent is False
    assert "could not be read" in identity.reason, identity.reason
    assert "unavailable" in identity.reason, identity.reason


def test_the_shared_readiness_establishes_the_exact_raw_split_pane(*, tmp_path: Path) -> None:
    """The NATIVE control at an OWNED fixture boundary: a pane this file itself split.

    The raw-split boundary is the one case where the exact created pane is knowable
    without going through the adapter at all, and it is where the measured fourth
    native failure landed — `_reading` taken immediately after a raw split got an
    unusable native process reading and failed the exercise before it reached any
    adapter.

    So the delivered :class:`PaneReadiness` is driven over a pane this control splits
    itself, on a real owned server running the declared minimal shell, and every part
    of what it establishes is read back rather than inferred: the exact pane, a real
    bounded child under that pane's own pinned retained shell, that child's own exit,
    the same shell identity owning its foreground again, and the pane's two shell
    descriptions agreeing about that same shell.

    The server is this exercise's own resource and is stopped by name.
    """
    session = f"overseer-test-{os.getpid()}-raw-split-readiness"
    server = start_owned_server(session=session, scratch=tmp_path, log_name="rawsplit.log")
    try:
        pane_id = split_pane(socket_path=server.socket_path, pane_id=server.root, direction="down")
        before = pane_ids(socket_path=server.socket_path)
        readiness = PaneReadiness(
            socket_path=server.socket_path, transient=startup_transient(scratch=tmp_path)
        )
        readiness.establish(pane_id=pane_id)
        gate = readiness.gate
        identity = readiness.identity
        surviving = pane_ids(socket_path=server.socket_path)
        staged_parent = (
            None
            if gate is None or gate.transient is None or gate.transient.pid is None
            else parent_pid_of(pid=gate.transient.pid)
        )
    finally:
        stop_owned_server(session=session)

    assert readiness.refusal() == "", readiness.refusal()
    assert readiness.panes == [pane_id], readiness.panes
    assert pane_id in before and pane_id in surviving, "the established pane must survive its setup"
    assert gate is not None and gate.gated == [pane_id], gate
    assert gate.transient is not None and gate.transient.pid is not None, gate.transient
    assert gate.retained is not None, "the raw-split pane's retained shell was never pinned"
    assert staged_parent in (None, gate.retained.pid), (
        f"the controlled child {gate.transient.pid} is not a child of the pinned retained "
        f"shell {gate.retained.pid}"
    )
    assert gate.departed == "", gate.departed
    assert gate.established is not None and gate.established.recovered is True, gate.established
    assert identity is not None and identity.coherent is True, readiness.refusal()
    assert identity.pane_id == pane_id, identity
    assert identity.shell_pid == gate.retained.pid, (
        f"the coherent identity describes shell {identity.shell_pid} while the pinned retained "
        f"shell is {gate.retained.pid}"
    )
    assert Path(identity.executable).name == identity.reported, (
        "the owned server declares a minimal shell whose reported name and kernel executable "
        f"agree by basename; this pane reported {identity!r}"
    )


def test_a_closed_exact_pane_is_a_bounded_fixture_refusal_with_its_server_cleaned_up(
    *, tmp_path: Path
) -> None:
    """Real, OWNED unavailability at the same boundary: the pane is closed first.

    The fixture closes the pane it is about to establish — its own resource, closed
    over the real socket — so the server genuinely has no reading to give for it.
    That must be a NAMED bounded refusal carrying the pane, never an establishment,
    and the owned server must still be stopped and deleted afterwards.

    The cleanup half is asserted from OUTSIDE: after teardown the session's socket is
    gone, so the exercise left no live server behind for the next one to collide with.
    """
    session = f"overseer-test-{os.getpid()}-closed-pane-readiness"
    server = start_owned_server(session=session, scratch=tmp_path, log_name="closed.log")
    try:
        pane_id = split_pane(socket_path=server.socket_path, pane_id=server.root, direction="down")
        readiness = PaneReadiness(
            socket_path=server.socket_path,
            transient=startup_transient(scratch=tmp_path),
            seconds=1.0,
            coherence_seconds=1.0,
            close_before_establishing=True,
        )
        readiness.establish(pane_id=pane_id)
    finally:
        stop_owned_server(session=session)

    refusal = readiness.refusal()
    assert refusal != "", "a closed pane established nothing, so the refusal must say so"
    assert readiness.panes == [pane_id], readiness.panes
    assert readiness.identity is None or readiness.identity.coherent is False, readiness.identity
    assert not session_socket(session=session).exists(), (
        f"the owned server for {session!r} outlived its exercise; a fixture failure must clean "
        "only its own resources, but it must clean them"
    )
