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

**The four measured fixture defects these replace.** All four were taken against
real herdr on the operator host, and none of them is evidence about the adapter.

  - **A transient startup process satisfied the occupation wait.** The old wait
    returned as soon as a pane's `foreground_process_group_id` differed from its
    `shell_pid` — any difference, by any process. Measured: shell `zsh` pid
    3584980, then foreground pid 3585294 named `mv`, a child of the operator
    shell's own startup. The wait returned immediately, the requested `sleep`
    was never observed, and the adapter then quite correctly launched into an
    idle shell — so the test that exists to prove a live occupant withholds the
    launch passed against a pane that had no occupant at all.
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
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


def startup_transient(*, scratch: Path) -> str:
    """A command that runs one real, self-terminating foreground child.

    A COPY of the system `sleep` under :data:`TRANSIENT_NAME`, so the process
    the kernel reports is genuine and its lifetime is this fixture's to choose
    rather than the host's. It stands in for the `mise` and `atuin` children the
    operator's `zsh` forks while a freshly created pane starts up — the measured
    condition under which the adapter legitimately refuses a launch.
    """
    source = shutil.which("sleep")
    assert source is not None, "a native exercise needs a real `sleep` binary to copy"
    binary = scratch / TRANSIENT_NAME
    if not binary.exists():
        _ = shutil.copy(source, binary)
    return f"{binary} {TRANSIENT_SECONDS}"


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
    """A poll whose clock advances only through `ticks`, and never really sleeps."""
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
