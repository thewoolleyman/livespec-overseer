"""A pane whose shell is registered under an ALIAS name is still a retained shell.

Native regression for a refusal that fires on a perfectly healthy host. The
retained-shell gate requires the server's reported name and the kernel's
executable to describe one program, and it decided that by comparing BASENAMES.
On a Debian-family host `/bin/sh` is a symlink to `dash`, so a pane rooted at
`/bin/sh` reports `name='sh'` while `/proc/<pid>/exe` resolves to
`/usr/bin/dash` — two truthful answers about one process, and the comparison
read them as a contradiction:

    herdr calls shell 623375 'sh' while the kernel runs '/usr/bin/dash';
    one of the two is wrong

Neither source was wrong. `sh` is what the shell was INVOKED as and `dash` is
what the kernel RESOLVED it to, and this host registers `/bin/sh` in
`/etc/shells` — so it is a supported login shell by the system's own answer.

**Why it was never seen until a janitor run.** Herdr roots a pane at `$SHELL`
and falls back to `/bin/sh` when that variable is absent. An interactive
operator shell exports `SHELL=/bin/bash`, so every pane came up as `bash`,
whose name and resolved executable agree. A gate invocation has no login shell
and therefore no `$SHELL`, so every pane came up as `sh` and EVERY positive
layout case refused. Measured on this host:

    SHELL=/bin/bash   name='bash'  exe=/usr/bin/bash  -> basenames agree
    SHELL unset       name='sh'    exe=/usr/bin/dash  -> basenames disagree
    SHELL=/bin/sh     name='sh'    exe=/usr/bin/dash  -> basenames disagree

So each server here is launched with an EXPLICIT environment rather than
inheriting the ambient one. That is what makes the regression deterministic in
both directions: the sh-context test would pass by accident under an operator
shell, and the bash-context control would stop being a control.

**The fix must not become a blanket acceptance, so the two register bounds below
hold it.** The alias table is the host's own shell register, and it is what
authorizes: an empty table and a table whose entry resolves to a DIFFERENT
binary must both still refuse the very same live pane. Only the registry may
mediate between a name and an executable; nothing here relaxes the rule that one
lying source refuses rather than decides.

**EVERY EXERCISE HERE GRADED ALIAS AUTHORIZATION AGAINST A PANE WHOSE OWN
IDENTITY THIS FIXTURE HAD NEVER ESTABLISHED, AND THAT IS WHAT IT WAS REPAIRED
FOR (work-item `overseer-3kojxx`).** `_start_server` reads a reported name and a
kernel executable for the workspace ROOT pane, and `_assert_alias_context`
asserts the host's alias premise against THAT reading. The public
`split_window_top` call then creates a DIFFERENT pane — the one the command
actually goes into, three round trips later — and nothing here ever established
anything about it. The measured consequence, from the unchanged full-cohort run
supplied with the work item (2026-10-07T12:31:07Z through 12:35:51Z, 1 failed /
3423 passed / 2 skipped):

    test_a_pane_whose_reported_name_needs_no_alias_still_receives_the_launch
    line 365, assert outcome.ok is True
    new pane w1:p2: herdr calls shell 2679865 'herdr' while the kernel runs
    '/usr/bin/bash'; one of the two is wrong

The product was RIGHT. Two sources disagreed about one process and it refused
rather than deciding, which is the whole rule this file exists to pin. What was
missing is the fixture's premise: the created pane's server-reported name and its
kernel executable were never OBSERVED to describe one program before the exercise
graded whether an alias authorized the write.

**That mismatch's origin is NOT established, and nothing here reconstructs it.**
It is not claimed to be pre-exec timing, server caching, or a host profile; no
run in this sandbox reproduced it. Two bounded probes were taken and are recorded
for what they are rather than for what they would be convenient to mean: with
`SHELL=/bin/bash`, three freshly split panes each reported `'bash'` against
`/usr/bin/bash` in their FIRST reading about a millisecond after the split reply,
and a 40-round repeat under 16 concurrent busy loops on 16 cores produced zero
incoherent first readings, with the slowest coherent reading at 6.1ms. Those
probes bound nothing about the host receipt above. They are why the premise is
established by a BOUNDED WAIT that reports its own expiry, rather than by a claim
that the condition is instant.

So the readiness of the EXACT created pane is now established between two of the
writer's own requests, and `_assert_established` grades it before any test grades
alias authorization — see :class:`_Readiness` for the mechanism and
:func:`_graded_launch` for the order.

**The writer is still entered through its own public `split_window_top`.** The
delivered `ReadyShellGate` is a `BoundedRequests` wrapper, so it COULD have been
wrapped around the writer and driven at `herdr_layout.place_above`; that is what
the sibling `tests/test_herdr_live_occupied_pane_launch.py` was corrected AWAY
from, because the public facade is part of what these exercises are about and a
sequence entered one layer below it is a different subject. That file moved its
establishment to the forwarding proxy it already owned. This file owns no proxy
and must not grow one: these exercises bind the writer to the REAL server's pid
and `/proc` start time, and a proxy would make the validated peer this test
process instead. So the boundary here is :class:`_ReadyWriter` — the shipped
writer with its PUBLIC `request` seam interposed, inheriting `split_window_top`,
`herdr_layout.place_above`, the real socket, the per-request deadline, the peer
revalidation and the host shell register unchanged.

Session isolation is herdr's own `--session` mechanism: every session name
carries this test process's pid, and teardown stops and deletes BY THAT EXACT
NAME, so no other session — including the operator's `default` — is touched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import claude_sessions
import herdr_identity
import herdr_protocol
import herdr_transport
import herdr_write
import pytest
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    TRANSIENT_SECONDS,
    BoundedPoll,
    ForegroundReading,
    ReadyShellGate,
    ShellRecovery,
    await_occupying_child,
    parent_pid_of,
    process_info_reply,
    raw_request,
    read_foreground,
    startup_transient,
)

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
LAUNCH_TIMEOUT = 20.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
LOGIN_SHELL_REGISTRY = "/etc/shells"

MARKER = "OVALIAS1"
LAUNCH_COMMAND = f"sleep 120 #{MARKER}"
LAUNCH_NAME = "sleep"
# A real binary that is emphatically not a shell, used to build an alias table
# that names the right shell and resolves to the wrong program.
NOT_A_SHELL = "/usr/bin/sleep"

# The bound each of the readiness establishment's waits runs under, and the poll
# interval between its real readings.
#
# It is deliberately generous, and it can be: the establishment completes BEFORE
# the writer's own request is handed to `herdr_transport`, so unlike the sibling
# occupied-pane exercise — which establishes at a forwarding proxy, INSIDE one
# request's single absolute deadline — nothing here is racing a transport
# timeout. Measured in this sandbox the whole establishment takes about three
# seconds.
READY_SECONDS = 20.0
READY_POLL = 0.1
# A bound short enough to expire WHILE the staged child is still running, and
# long enough to take several real readings first. The child outlives it by a
# second, so the refusal it proves is about the pane's state rather than about
# which of two timers won.
IMPATIENT_SECONDS = 1.0


@dataclass(frozen=True, kw_only=True)
class LiveServer:
    """One live herdr server child, its socket, its ROOT pane and that pane's shell.

    `reported_name` and `kernel_executable` describe the WORKSPACE ROOT, which is
    the pane `_assert_alias_context` asserts the host's alias premise against.
    They are deliberately NOT a claim about the pane an exercise writes into: that
    pane is created by the adapter, and establishing anything about it is the
    whole job of :class:`_Readiness`.
    """

    session: str
    socket_path: str
    server_pid: int
    root: str
    reported_name: str
    kernel_executable: str


@dataclass(frozen=True, kw_only=True)
class _RegisteredShell:
    """One `/etc/shells` entry, as the host DECLARES it beside what it resolves to.

    The declared form is kept because the NAME is the load-bearing half: an alias
    is a name this host registers a login shell under, and that name is
    unanswerable once the declared path has been resolved away.
    """

    declared: str
    name: str
    resolved: str


def _socket_for(*, session: str) -> Path:
    return Path.home() / ".config" / "herdr" / "sessions" / session / "herdr.sock"


def _cli(*, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, *args], capture_output=True, text=True, timeout=60, check=False
    )


def _reading(*, socket_path: str, pane_id: str) -> ForegroundReading:
    """`pane_id`'s live process reading, over a raw socket, or a FIXTURE failure.

    Control evidence must not come from the surface under test, or the file would
    only prove the adapter is self-consistent. An unusable reply stops the
    exercise here rather than raising out of whichever assertion first touched a
    field the server never sent.
    """
    reading = read_foreground(reply=process_info_reply(socket_path=socket_path, pane_id=pane_id))
    assert reading is not None, f"herdr returned no usable process reading for {pane_id!r}"
    return reading


def _leader_name(*, reading: ForegroundReading) -> str:
    """The name the server gives the entry that OWNS the foreground group, or ``""``.

    Empty when the reply names no single leader, which is an unusable reading
    rather than an approximation — the same discrimination the adapter's own
    reader makes.
    """
    named = [name for pid, name in reading.processes if pid == reading.group_id]
    return named[0] if len(named) == 1 else ""


def _kernel_executable(*, pid: int) -> str | None:
    """`pid`'s resolved `/proc/<pid>/exe`, or None when the KERNEL half is unavailable.

    `readlink` rather than a realpath of the magic link: resolving the path of a
    process that is GONE answers `/proc/<pid>/exe` unchanged, which would
    manufacture an executable for a dead pid. The target is then resolved so a
    host where `/bin/bash` symlinks to `/usr/bin/bash` compares equal either way.

    This is the FIXTURE's own instrument, deliberately not the adapter's reader:
    an exercise that took its premise from the surface under test would only
    prove that surface self-consistent.
    """
    try:
        target = Path(f"/proc/{pid}/exe").readlink()
    except OSError:
        return None
    return str(target.resolve())


def _registered_shells() -> tuple[_RegisteredShell, ...]:
    """Every login shell `/etc/shells` declares, with the name it declares it under.

    The host's own register, read here rather than enumerated: `("sh",
    "/usr/bin/dash")` on a Debian-family host comes from the declared `/bin/sh`.
    An empty result is possible and is not special-cased — it means this host
    mediates nothing, which makes every alias premise below refuse.
    """
    try:
        raw = Path(LOGIN_SHELL_REGISTRY).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return tuple(
        _RegisteredShell(declared=entry, name=Path(entry).name, resolved=os.path.realpath(entry))
        for entry in (line.strip() for line in raw.splitlines())
        if entry and not entry.startswith("#")
    )


@dataclass(frozen=True, kw_only=True)
class _ShellCoherence:
    """ONE pane's server-reported shell name against the KERNEL's executable for it.

    The facts are carried even on a refusal, because they are what a fixture
    failure has to NAME: which pane, which shell pid, what the server called it,
    and what the kernel runs. `mediated_by` is the `/etc/shells` entry that
    reconciled the two, and is empty when the basenames already agreed.
    """

    pane_id: str
    shell_pid: int
    reported: str
    executable: str
    mediated_by: str
    coherent: bool
    reason: str


def _no_coherence(*, pane_id: str, reason: str) -> _ShellCoherence:
    """An observation that established nothing, carrying only why."""
    return _ShellCoherence(
        pane_id=pane_id,
        shell_pid=0,
        reported="",
        executable="",
        mediated_by="",
        coherent=False,
        reason=reason,
    )


def _coherence_of(
    *, reading: ForegroundReading, pane_id: str, registered: tuple[_RegisteredShell, ...]
) -> _ShellCoherence:
    """Whether `reading` shows ONE program answering to two truthful descriptions.

    Four conditions, all required, because the question is only meaningful about
    an idle shell this pane actually owns:

      1. the reading is about `pane_id` and not about some other pane;
      2. the pane's own retained shell owns its foreground group, so the leader
         the server names IS that shell rather than a child of it;
      3. the kernel answers for that pid at all — an unreadable `/proc/<pid>/exe`
         is UNAVAILABLE evidence, never agreement;
      4. the two descriptions agree: equal basenames, or a name this host
         registers for EXACTLY the executable the kernel reports. Matching the
         name alone would reinstate the single-source trust the agreement rule
         exists to prevent.
    """
    if reading.pane_id != pane_id:
        return _no_coherence(
            pane_id=pane_id,
            reason=f"the reading describes pane {reading.pane_id!r}, not {pane_id!r}",
        )
    if not reading.is_idle():
        return _no_coherence(
            pane_id=pane_id,
            reason=(
                f"{pane_id!r} is OCCUPIED: foreground group {reading.group_id} is not its "
                f"retained shell {reading.shell_pid}, so its leader is not the shell"
            ),
        )
    reported = _leader_name(reading=reading)
    if not reported:
        return _no_coherence(
            pane_id=pane_id,
            reason=f"the reply names no single foreground group leader: {list(reading.processes)}",
        )
    executable = _kernel_executable(pid=reading.shell_pid)
    if executable is None:
        return _no_coherence(
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
    return _ShellCoherence(
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


def _await_coherent_shell(
    *,
    socket_path: str,
    pane_id: str,
    poll: BoundedPoll,
    registered: tuple[_RegisteredShell, ...],
) -> _ShellCoherence:
    """Poll real readings until `pane_id`'s two shell descriptions agree, or say why not.

    The expiry is REPORTED, carrying the last thing seen. A wait that fell out of
    its bound silently is exactly how a fixture comes to grade the adapter on a
    premise it never established — see this module's docstring for the measured
    host receipt that premise was missing for.
    """
    deadline = poll.monotonic() + poll.seconds
    verdict = _no_coherence(
        pane_id=pane_id, reason="no process reading was taken before the deadline"
    )
    while poll.monotonic() < deadline:
        reading = read_foreground(
            reply=process_info_reply(socket_path=socket_path, pane_id=pane_id)
        )
        if reading is None:
            verdict = _no_coherence(
                pane_id=pane_id,
                reason="the herdr process reading carried no usable shell/foreground fields",
            )
        else:
            verdict = _coherence_of(reading=reading, pane_id=pane_id, registered=registered)
            if verdict.coherent:
                return verdict
        poll.sleep(READY_POLL)
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

    `ReadyShellGate` establishes a pane's readiness around a request it then
    forwards to whatever it wraps. Here what it wraps is this: a raw round trip
    taken on the FIXTURE's own behalf. So the gate's reading is unmistakably a
    setup observation — it is not a request the writer made, and it is recorded in
    neither :meth:`_Readiness.writer_methods` nor
    :meth:`_Readiness.writer_deliveries`.

    `target` and `expect` are the protocol's peer-validation and
    envelope-expectation arguments, which only a real writer acts on; this
    forwarder ignores both, and its reply is consumed by the gate and discarded.
    """

    socket_path: str

    def request(
        self, *, target: Any, method: str, params: Mapping[str, object], expect: Any
    ) -> dict[str, Any]:
        return raw_request(socket_path=self.socket_path, method=method, params=dict(params))


@dataclass(kw_only=True)
class _Readiness:
    """The EXACT created pane's readiness, established once, and what the writer sent.

    Two independent observations, in this order, both about the pane the adapter
    just created and neither taken from the adapter:

      1. the delivered :class:`ReadyShellGate` — one real bounded child staged in
         that pane, OBSERVED running under the pane's own retained shell, that
         shell pinned as an IDENTITY (pid AND start time), the child observed
         exiting on its OWN, and the same identity observed owning its foreground
         again. None of that is re-coded here;
      2. :func:`_await_coherent_shell` — the pane's server-reported shell name and
         the kernel's executable for that shell observed to describe ONE program,
         by basename or by this host's own `/etc/shells` register. This is the
         premise the measured host receipt in the module docstring was missing.

    `registered` is the FIXTURE's own reading of the host register, used only for
    the premise in (2). It is never handed to the adapter, whose own
    `shell_aliases` is what the exercises grade.

    `writer_requests` is the writer's OWN request stream, recorded at the seam
    :class:`_ReadyWriter` interposes. The gate's traffic never enters it: the
    staged child and the gate's own reading both go to the real socket on raw
    connections, so a zero-delivery claim describes the surface under test alone.
    """

    socket_path: str
    transient: str
    registered: tuple[_RegisteredShell, ...]
    seconds: float = READY_SECONDS
    coherence_seconds: float = READY_SECONDS
    # Real, OWNED unavailability, for the control below: the fixture closes the
    # pane it is about to establish, so the server genuinely has no reading to
    # give for it. Never set by an exercise.
    close_before_establishing: bool = False
    panes: list[str] = field(default_factory=list)
    gate: ReadyShellGate | None = None
    coherence: _ShellCoherence | None = None
    writer_requests: list[dict[str, Any]] = field(default_factory=list)

    def writer_methods(self) -> list[str]:
        return [str(request["method"]) for request in self.writer_requests]

    def writer_deliveries(self) -> list[tuple[str, str, tuple[str, ...]]]:
        """Every `(pane, text, keys)` the WRITER delivered — this fixture's setup excluded.

        The keys are carried because the launch is ONE atomic text-plus-Enter
        call, so an empty list is the byte-level statement that neither the
        command nor its submission reached any pane.
        """
        return [
            (
                str(request["params"].get("pane_id")),
                str(request["params"].get("text")),
                tuple(str(key) for key in request["params"].get("keys", [])),
            )
            for request in self.writer_requests
            if request["method"] == herdr_protocol.METHOD_PANE_SEND_INPUT
        ]

    def establish(self, *, pane_id: str) -> None:
        """Establish both observations for `pane_id`, REPORTING rather than raising.

        A raise here would surface as whatever the writer's next request happened
        to do, which is how a fixture comes to grade an establishment it never
        made. Every failure is recorded and answered by :meth:`refusal`.
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
            self.coherence = _await_coherent_shell(
                socket_path=self.socket_path,
                pane_id=pane_id,
                poll=BoundedPoll(seconds=self.coherence_seconds),
                registered=self.registered,
            )
        except OSError as failed:
            gate.established = ShellRecovery(
                recovered=False, reason=f"the readiness step failed: {failed}"
            )

    def refusal(self) -> str:
        """Why this fixture did NOT establish the created pane's readiness, or ``""``."""
        if self.gate is None:
            return "the readiness step never ran, so nothing about the created pane is established"
        if self.gate.refusal():
            return self.gate.refusal()
        if self.coherence is None:
            return "the created pane's server/kernel shell identity was never observed at all"
        return self.coherence.reason


@dataclass(frozen=True, kw_only=True)
class _ReadyWriter(herdr_write.HerdrWriter):
    """The SHIPPED writer, with the created pane's readiness established mid-sequence.

    `split_window_top` is INHERITED verbatim — this class adds no facade, and
    `_split_top` asserts that identity rather than trusting it. So the sequence,
    the proofs, the `ShellProof` built from this writer's own fields, the socket,
    the per-request deadline and the peer revalidation are all the shipped
    facade's.

    The one interposition is at `request`, which is PUBLIC precisely because
    `herdr_layout` runs its whole sequence on it. Before the FIRST
    `pane.process_info` naming a pane, and only the first, the readiness
    establishment runs; then the writer's own request goes through unchanged.

    **Why that request and not a later seam.** `shell_evidence_of` is also
    injectable and would be a smaller hook, but it is called INSIDE
    `_herdr_shell_identity.retained_shell`, after the server's reading has
    already been accepted — a created pane that is still busy refuses one step
    earlier, with the establishment never reached. The condition has to be
    established BEFORE the adapter's first reading is taken, which is what this
    seam is.

    **And the establishment costs no request its deadline**, because it completes
    before `super().request` hands anything to `herdr_transport`.
    """

    readiness: _Readiness

    def request(
        self,
        *,
        target: herdr_identity.HerdrPaneTarget,
        method: str,
        params: Mapping[str, object],
        expect: herdr_protocol.ReplyExpectation,
    ) -> herdr_transport.RpcOutcome:
        pane_id = str(params.get("pane_id", ""))
        self.readiness.writer_requests.append({"method": method, "params": dict(params)})
        first_reading = (
            method == herdr_protocol.METHOD_PANE_PROCESS_INFO
            and bool(pane_id)
            and pane_id not in self.readiness.panes
        )
        if first_reading:
            self.readiness.establish(pane_id=pane_id)
        return super().request(target=target, method=method, params=params, expect=expect)


def _capture(*, socket_path: str, pane_id: str) -> str:
    reply = raw_request(
        socket_path=socket_path,
        method=herdr_protocol.METHOD_PANE_READ,
        params={"pane_id": pane_id, "source": "visible", "format": "text", "strip_ansi": True},
    )
    return str(reply["result"]["read"]["text"])


def _pane_ids(*, socket_path: str) -> list[str]:
    reply = raw_request(socket_path=socket_path, method=herdr_protocol.METHOD_PANE_LIST, params={})
    return [str(pane["pane_id"]) for pane in reply["result"]["panes"]]


def _start_server(*, session: str, scratch: Path, shell_path: str | None) -> LiveServer:
    """A server whose panes are rooted at `shell_path`, or at herdr's own fallback.

    The environment is built EXPLICITLY — `$SHELL` removed rather than merely
    left alone — because the whole subject of this file is which shell the pane
    comes up as, and inheriting the ambient value would make that the operator's
    choice rather than the test's.

    The identity read here is the ROOT pane's, which is what the host's alias
    premise is asserted against. It says nothing about the pane an exercise
    writes into; that one is established by :class:`_Readiness`.
    """
    environment = dict(os.environ)
    if shell_path is None:
        _ = environment.pop("SHELL", None)
    else:
        environment["SHELL"] = shell_path
    log_name = f"{session.rsplit('-', 1)[-1]}.log"
    log = (scratch / log_name).open("wb")
    child = subprocess.Popen(  # noqa: S603 — the herdr CLI, not a Python child
        [HERDR_BINARY, "--session", session, "server"],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(scratch),
        env=environment,
    )
    address = _socket_for(session=session)
    deadline = time.monotonic() + SERVER_READY_TIMEOUT
    while time.monotonic() < deadline and not address.exists():
        time.sleep(READY_POLL)
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
    root = str(created["result"]["root_pane"]["pane_id"])
    reading = _reading(socket_path=str(address), pane_id=root)
    executable = _kernel_executable(pid=reading.shell_pid)
    assert executable is not None, f"the root pane's shell {reading.shell_pid} must be readable"
    return LiveServer(
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        root=root,
        reported_name=_leader_name(reading=reading),
        kernel_executable=executable,
    )


def _serve(*, scratch: Path, label: str, shell_path: str | None) -> Iterator[LiveServer]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    session = f"overseer-test-{os.getpid()}-alias-{label}"
    server = _start_server(session=session, scratch=scratch, shell_path=shell_path)
    try:
        yield server
    finally:
        _ = _cli(args=["--session", session, "server", "stop"])
        _ = _cli(args=["session", "delete", session])


@pytest.fixture(name="alias_server")
def _alias_server(*, tmp_path: Path) -> Iterator[LiveServer]:
    """A server with NO `$SHELL`, so herdr roots its panes at `/bin/sh`."""
    yield from _serve(scratch=tmp_path, label="sh", shell_path=None)


@pytest.fixture(name="exact_server")
def _exact_server(*, tmp_path: Path) -> Iterator[LiveServer]:
    """A server with `SHELL=/bin/bash`, whose reported name needs no alias."""
    yield from _serve(scratch=tmp_path, label="bash", shell_path="/bin/bash")


def _readiness_for(*, server: LiveServer, scratch: Path, **overrides: Any) -> _Readiness:
    """One establishment's worth of state, with the host's real register read fresh."""
    return _Readiness(
        socket_path=server.socket_path,
        transient=startup_transient(scratch=scratch),
        registered=_registered_shells(),
        **overrides,
    )


def _split_top(*, server: LiveServer, readiness: _Readiness, command: str, **overrides: Any) -> Any:
    """The writer's own PUBLIC entrypoint, unchanged, against the REAL server.

    `HerdrWriter.split_window_top` is what this exercise is about, so it is what
    is called, and the inherited-facade assertion below is what keeps that from
    being merely a claim: a fixture that had overridden it would fail here rather
    than quietly grading a different subject. The target names the REAL server's
    pid and `/proc` start time, so the generation every step revalidates is the
    server's own.
    """
    starttime = claude_sessions.proc_starttime(pid=server.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    assert (
        _ReadyWriter.split_window_top is herdr_write.HerdrWriter.split_window_top
    ), "the exercise must enter the SHIPPED public facade, not a fixture reimplementation"
    return _ReadyWriter(readiness=readiness, **overrides).split_window_top(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=server.socket_path,
            server_pid=server.server_pid,
            server_starttime=starttime,
            pane_id=server.root,
        ),
        cwd=PANE_CWD,
        command=command,
        ratio=TOP_RATIO,
    )


def _assert_established(*, readiness: _Readiness, pane_id: str) -> _ShellCoherence:
    """Grade the created pane's readiness premise, naming whichever part was missing.

    Every fact is asserted separately so a failure says which one: the step RAN
    exactly once and for the pane the writer created, the gate established what it
    establishes, the controlled child was the pinned shell's own, it exited, that
    shell recovered, and the pane's two shell descriptions agree about it. An
    unavailable or expired observation therefore fails HERE — as a delivered
    fixture assertion carrying the bound it expired under — and is never reported
    as the adapter declining a launch.
    """
    assert len(readiness.panes) == 1, (
        "the readiness step must have run exactly once, for the pane the writer created; "
        f"it ran for {readiness.panes} while the writer sent {readiness.writer_methods()}"
    )
    established = readiness.panes[0]
    assert not pane_id or established == pane_id, (
        f"readiness was established for {established!r} but the writer reported creating "
        f"{pane_id!r}"
    )
    assert readiness.refusal() == "", f"{established!r} readiness: {readiness.refusal()}"
    gate = readiness.gate
    assert gate is not None, "a refusal-free run established something, so it must hold a gate"
    transient = gate.transient
    assert transient is not None and transient.pid is not None, transient
    assert gate.retained is not None, "the created pane's retained shell was never pinned"
    assert parent_pid_of(pid=transient.pid) in (None, gate.retained.pid), (
        f"the controlled child {transient.pid} is not a child of the pinned retained "
        f"shell {gate.retained.pid}"
    )
    assert gate.departed == "", gate.departed
    recovery = gate.established
    assert recovery is not None and recovery.recovered is True, recovery
    coherence = readiness.coherence
    assert coherence is not None and coherence.coherent is True, readiness.refusal()
    assert coherence.shell_pid == gate.retained.pid, (
        f"the coherent identity describes shell {coherence.shell_pid} while the pinned "
        f"retained shell is {gate.retained.pid}"
    )
    return coherence


def _graded_launch(
    *, server: LiveServer, readiness: _Readiness, command: str = LAUNCH_COMMAND, **overrides: Any
) -> tuple[Any, _ShellCoherence]:
    """Run the public facade, then GRADE the fixture premise before returning an outcome.

    The ORDER is what
    `test_unavailable_or_expired_readiness_fails_before_alias_authorization_is_graded`
    is about: no caller can reach an assertion about alias authorization without
    the created pane's readiness having been established first, because the
    grading happens HERE rather than in each test.
    """
    outcome = _split_top(server=server, readiness=readiness, command=command, **overrides)
    return outcome, _assert_established(readiness=readiness, pane_id=outcome.pane_id)


def _assert_alias_context(*, server: LiveServer) -> _RegisteredShell:
    """The precondition is ASSERTED, never assumed: name and executable differ.

    If this host's `/bin/sh` were itself bash, the names would agree and the
    defect under test could not arise — so the condition is measured and the test
    skips rather than passing vacuously. The mediating entry is returned so an
    exercise can assert the adapter's own register carries it too.
    """
    kernel_name = Path(server.kernel_executable).name
    if kernel_name == server.reported_name:
        pytest.skip(
            f"this host's fallback shell reports {server.reported_name!r} and resolves to "
            f"{server.kernel_executable!r}; there is no alias to mediate"
        )
    assert server.reported_name == "sh", (
        f"fixture precondition: a server with no $SHELL must root its panes at sh, "
        f"not {server.reported_name!r}"
    )
    assert Path(
        LOGIN_SHELL_REGISTRY
    ).is_file(), "fixture precondition: this host registers login shells"
    registered = _registered_shells()
    mediating = [
        entry
        for entry in registered
        if entry.name == server.reported_name and entry.resolved == server.kernel_executable
    ]
    assert mediating, (
        f"fixture precondition: {LOGIN_SHELL_REGISTRY} must register {server.reported_name!r} as "
        f"a name for {server.kernel_executable!r}; it registers "
        f"{sorted(entry.declared for entry in registered)}"
    )
    return mediating[0]


def _observe_launched_child(*, socket_path: str, pane_id: str, shell_pid: int) -> int:
    """The pid of the single `sleep` running under `pane_id`'s own retained shell.

    Identified by the requested NAME, by the pane's foreground group, and by the
    ESTABLISHED shell as its `/proc` parent — so "it ran under that same shell" is
    a claim about the shell whose identity the readiness step proved coherent,
    rather than about whichever shell the pane happened to report afterwards.
    """
    observed = await_occupying_child(
        read=lambda: process_info_reply(socket_path=socket_path, pane_id=pane_id),
        name=LAUNCH_NAME,
        poll=BoundedPoll(seconds=LAUNCH_TIMEOUT),
    )
    assert observed.pid is not None, observed.reason
    assert parent_pid_of(pid=observed.pid) == shell_pid, (
        f"the launched process {observed.pid} is not a child of the established retained "
        f"shell {shell_pid}"
    )
    assert observed.pid != shell_pid, "the command must run UNDER the shell, not replace it"
    return observed.pid


def test_a_pane_rooted_at_an_alias_of_a_registered_shell_receives_the_launch(
    *, alias_server: LiveServer, tmp_path: Path
):
    """The regression: a `/bin/sh` pane on a dash host is a retained shell.

    Driven through the adapter's own default readers, so the host's real
    `/etc/shells` and real `/proc` are what authorize the write — the same
    configuration a gate run uses. The launched process must be the SHELL'S
    child, which is what distinguishes a reusable retained-shell pane from one an
    `exec` launch would take down with its first command.

    The created pane's readiness is established first, and the identity it
    establishes is asserted to be the MEDIATED one: the pane really reports a name
    the kernel's executable does not match by basename, and the entry that
    reconciles them is an `/etc/shells` entry the adapter's own register carries
    too. So this is the alias path being exercised, not a pane that happened to
    come up as bash.
    """
    mediating = _assert_alias_context(server=alias_server)
    readiness = _readiness_for(server=alias_server, scratch=tmp_path)

    outcome, coherence = _graded_launch(server=alias_server, readiness=readiness)

    assert outcome.ok is True, outcome.error
    assert coherence.mediated_by == mediating.declared, (
        f"the created pane's identity was reconciled by {coherence.mediated_by!r}, not by the "
        f"host entry {mediating.declared!r} this exercise is about"
    )
    assert Path(coherence.executable).name != coherence.reported, coherence
    assert (
        (coherence.reported, coherence.executable) in herdr_write.HerdrWriter().shell_aliases
    ), "the adapter's own register must carry the pair the fixture observed"
    _ = _observe_launched_child(
        socket_path=alias_server.socket_path,
        pane_id=outcome.pane_id,
        shell_pid=coherence.shell_pid,
    )
    assert readiness.writer_deliveries() == [
        (outcome.pane_id, LAUNCH_COMMAND, ("Enter",))
    ], readiness.writer_deliveries()
    assert outcome.pane_id in _pane_ids(
        socket_path=alias_server.socket_path
    ), "the pane must survive its own first command"
    assert MARKER in _capture(socket_path=alias_server.socket_path, pane_id=outcome.pane_id)


def test_a_pane_whose_reported_name_needs_no_alias_still_receives_the_launch(
    *, exact_server: LiveServer, tmp_path: Path
):
    """The bash-context control, so the sh case is not passing for harness reasons.

    This is the path that was already green under an operator shell. It is kept
    beside the alias case because the two differ in exactly one input — the
    server's `$SHELL` — and a fix that broke this one would be trading a refusal
    for a different refusal.

    **This is the exercise the supplied host cohort FAILED, and its premise is
    what changed.** It graded `outcome.ok is True` against a pane whose own
    identity it had never established, and the host's created pane `w1:p2`
    reported `'herdr'` against a kernel executable of `/usr/bin/bash` — a real
    disagreement the adapter was right to refuse. The created pane's two
    descriptions are now observed to agree BEFORE the launch is graded, and the
    agreement asserted here is the EXACT-NAME one: nothing mediated it.
    """
    assert exact_server.reported_name == Path(exact_server.kernel_executable).name, (
        f"fixture precondition: {exact_server.reported_name!r} and "
        f"{exact_server.kernel_executable!r} must already agree without an alias"
    )
    readiness = _readiness_for(server=exact_server, scratch=tmp_path)

    outcome, coherence = _graded_launch(server=exact_server, readiness=readiness)

    assert outcome.ok is True, outcome.error
    assert coherence.mediated_by == "", (
        f"this exercise is the exact-name path, but {coherence.pane_id!r} needed "
        f"{coherence.mediated_by!r} to reconcile {coherence.reported!r} with "
        f"{coherence.executable!r}"
    )
    assert Path(coherence.executable).name == coherence.reported, coherence
    _ = _observe_launched_child(
        socket_path=exact_server.socket_path,
        pane_id=outcome.pane_id,
        shell_pid=coherence.shell_pid,
    )
    assert readiness.writer_deliveries() == [
        (outcome.pane_id, LAUNCH_COMMAND, ("Enter",))
    ], readiness.writer_deliveries()
    assert MARKER in _capture(socket_path=exact_server.socket_path, pane_id=outcome.pane_id)


def _assert_alias_denial(
    *, outcome: Any, coherence: _ShellCoherence, readiness: _Readiness
) -> None:
    """The refusal is the ALIAS-AUTHORIZATION one, about the pane just established.

    Asserted by its own terms rather than by `ok is False`, which any earlier
    guard would also satisfy: the error must name the ESTABLISHED shell's pid, the
    name the server reported for it and the executable the kernel runs, and the
    partial layout must survive with nothing delivered.
    """
    assert outcome.ok is False, "an unmediated name disagreement must refuse the launch"
    assert outcome.effect_unknown is False, "the split was enumerated, so the layout is known"
    assert outcome.pane_id == coherence.pane_id, (
        "the created pane is reported so the partial layout can be re-observed: "
        f"{outcome.pane_id!r} against the established {coherence.pane_id!r}"
    )
    assert str(coherence.shell_pid) in outcome.error, outcome.error
    assert repr(coherence.reported) in outcome.error, outcome.error
    assert repr(coherence.executable) in outcome.error, outcome.error
    assert "one of the two is wrong" in outcome.error, outcome.error
    assert (
        readiness.writer_deliveries() == []
    ), f"a refused launch delivers no command or Enter bytes: {readiness.writer_deliveries()}"


def test_the_host_registry_is_what_authorizes_an_alias_and_nothing_else(
    *, alias_server: LiveServer, tmp_path: Path
):
    """With no registered aliases, the very same live pane must still refuse.

    The bound that keeps the repair from being a relaxed name comparison. An
    empty table is the host declining to mediate, and the safe direction for a
    write is to refuse — so this drives the real sh pane, the real kernel reading,
    and an EMPTY alias table.

    The pane's own readiness is established FIRST, so the refusal asserted here is
    the alias-authorization guard meeting an empty register — not that guard
    meeting a pane that was occupied, unreadable or incoherent, which is the shape
    the control below stages deliberately.
    """
    _ = _assert_alias_context(server=alias_server)
    readiness = _readiness_for(server=alias_server, scratch=tmp_path)

    outcome, coherence = _graded_launch(
        server=alias_server, readiness=readiness, shell_aliases=frozenset()
    )

    assert coherence.mediated_by, "precondition: the host DOES mediate this pane's two names"
    _assert_alias_denial(outcome=outcome, coherence=coherence, readiness=readiness)
    assert outcome.pane_id in _pane_ids(
        socket_path=alias_server.socket_path
    ), "a refusal must preserve the partial layout rather than tear it down"
    assert MARKER not in _capture(
        socket_path=alias_server.socket_path, pane_id=outcome.pane_id
    ), "a refused launch must deliver no command bytes"


def test_an_alias_naming_the_right_shell_but_the_wrong_binary_is_refused(
    *, alias_server: LiveServer, tmp_path: Path
):
    """A registered name must resolve to the executable the KERNEL reports.

    The second bound, and the sharper one: the table names `sh`, exactly as the
    server does, but maps it to a program this pane is not running. Matching the
    name alone would accept it, which would reinstate the single-source trust the
    agreement rule exists to prevent.

    The established identity is what makes that precise — the wrong binary is
    asserted to differ from the executable the kernel actually reports for THIS
    pane's shell, rather than from an assumption about what the pane is running.
    """
    _ = _assert_alias_context(server=alias_server)
    readiness = _readiness_for(server=alias_server, scratch=tmp_path)

    outcome, coherence = _graded_launch(
        server=alias_server,
        readiness=readiness,
        shell_aliases=frozenset({("sh", NOT_A_SHELL)}),
    )

    assert coherence.reported == "sh", coherence
    assert coherence.executable != NOT_A_SHELL, (
        f"precondition: the injected alias must name a program this pane is NOT running; "
        f"the kernel reports {coherence.executable!r}"
    )
    _assert_alias_denial(outcome=outcome, coherence=coherence, readiness=readiness)
    assert MARKER not in _capture(
        socket_path=alias_server.socket_path, pane_id=outcome.pane_id
    ), "a refused launch must deliver no command bytes"


def _refused_premise(*, server: LiveServer, readiness: _Readiness) -> str:
    """Run the graded exercise and return the FIXTURE assertion it refused with.

    The empty-register exercise is the carrier deliberately: what this proves is
    that its alias denial cannot be reached on an unestablished premise. So the
    message is asserted NOT to be the alias verdict, and the writer is asserted to
    have delivered nothing on the way.
    """
    with pytest.raises(AssertionError) as refused:
        _ = _graded_launch(server=server, readiness=readiness, shell_aliases=frozenset())
    message = str(refused.value)
    assert (
        "one of the two is wrong" not in message
    ), f"the alias-authorization verdict was graded on an unestablished premise: {message}"
    assert readiness.writer_deliveries() == [], readiness.writer_deliveries()
    return message


def test_unavailable_or_expired_readiness_fails_before_alias_authorization_is_graded(
    *, alias_server: LiveServer, tmp_path: Path
):
    """Three real ways the premise fails, each a NAMED bounded fixture refusal.

    Every leg runs the same empty-register exercise the test above does, on the
    same live server, through the same public facade — and every one must fail as
    a FIXTURE assertion naming what it saw, before any alias verdict is graded.
    Without this control, that exercise's refusal could be a pane that was merely
    unready, and it would read identically.

    The legs, and what is real in each:

      1. **Unavailable.** The fixture CLOSES the pane it is about to establish —
         an owned resource, closed over the real socket — so the server genuinely
         has no reading to give for it. The refusal names the unusable reading.
      2. **Expired.** The bound is cut to one second while the staged child really
         runs for two, so one of the gate's OWN waits expires. Which one is a race
         this control does not pretend to settle — either the child is not
         observed within the bound, or it is observed and does not exit within it
         — so both are accepted, and what is asserted is the BOUND.
      3. **Incoherent identity, expired.** The pane really reports `sh` against a
         kernel executable of `dash`. With the FIXTURE's own mediation table
         narrowed to nothing — its instrument, never the adapter's register, which
         is untouched in this leg — the coherence wait has nothing to reconcile
         them with and expires naming the exact pane, shell pid, reported name and
         executable.
    """
    mediating = _assert_alias_context(server=alias_server)

    unavailable = _readiness_for(
        server=alias_server,
        scratch=tmp_path,
        seconds=IMPATIENT_SECONDS,
        coherence_seconds=IMPATIENT_SECONDS,
        close_before_establishing=True,
    )
    unavailable_refusal = _refused_premise(server=alias_server, readiness=unavailable)
    assert "no usable shell/foreground fields" in unavailable_refusal, unavailable_refusal
    assert unavailable.panes, "the readiness step must still have named the pane it was given"
    assert unavailable.panes[0] in unavailable_refusal, unavailable_refusal

    expired = _readiness_for(
        server=alias_server,
        scratch=tmp_path,
        seconds=IMPATIENT_SECONDS,
        coherence_seconds=IMPATIENT_SECONDS,
    )
    expired_refusal = _refused_premise(server=alias_server, readiness=expired)
    assert TRANSIENT_SECONDS > IMPATIENT_SECONDS, "the staged child must outlive the cut bound"
    assert f"within {IMPATIENT_SECONDS}s" in expired_refusal, expired_refusal
    assert (
        "was never observed" in expired_refusal or "never exited" in expired_refusal
    ), expired_refusal

    incoherent = _readiness_for(
        server=alias_server, scratch=tmp_path, coherence_seconds=IMPATIENT_SECONDS
    )
    incoherent.registered = ()
    incoherent_refusal = _refused_premise(server=alias_server, readiness=incoherent)
    observed = incoherent.coherence
    assert observed is not None and observed.coherent is False, observed
    assert observed.reported == mediating.name, observed
    assert observed.executable == mediating.resolved, observed
    assert "never reported a coherent shell identity within" in incoherent_refusal
    assert repr(observed.reported) in incoherent_refusal, incoherent_refusal
    assert repr(observed.executable) in incoherent_refusal, incoherent_refusal


def test_the_readiness_step_observes_a_real_bounded_child_in_the_exact_created_pane(
    *, alias_server: LiveServer, tmp_path: Path
):
    """The establishment's own evidence, read back from the server rather than inferred.

    The exercises above assert `refusal() == ""`, which a step that established
    nothing could not produce — but a reader cannot see from that WHICH pane was
    established in, nor that the controlled child was real. Both are measurements
    here: the step ran for exactly the pane the writer created and no other, that
    pane is one that did not exist beforehand, the writer still took BOTH of its
    own readings, and the staged child was a real process under that pane's own
    pinned retained shell.

    The staged child is the weaker claim deliberately: a bounded DISCRIMINATING
    instance of a non-idle created pane, not a reproduction of the operator host's
    `zsh`/`mise`/`atuin` startup, and not a reproduction of the contradictory
    identity this module's docstring records.
    `tests/test_herdr_live_observations.py` carries that framing in full.
    """
    _ = _assert_alias_context(server=alias_server)
    readiness = _readiness_for(server=alias_server, scratch=tmp_path)
    before = _pane_ids(socket_path=alias_server.socket_path)

    outcome, coherence = _graded_launch(server=alias_server, readiness=readiness)

    assert outcome.ok is True, outcome.error
    assert readiness.panes == [outcome.pane_id], readiness.panes
    assert outcome.pane_id not in before, "the established pane must be the one just CREATED"
    assert readiness.writer_methods().count(herdr_protocol.METHOD_PANE_PROCESS_INFO) == 2, (
        "the writer must still take BOTH its own readings — the establish and the recheck: "
        f"{readiness.writer_methods()}"
    )
    gate = readiness.gate
    assert gate is not None
    staged = gate.transient
    assert staged is not None and staged.pid is not None, staged
    assert staged.pid != coherence.shell_pid, "the staged child is not the pane's own shell"
    assert gate.retained is not None and gate.retained.pid == coherence.shell_pid, gate.retained
    assert (
        _reading(socket_path=alias_server.socket_path, pane_id=outcome.pane_id).shell_pid
        == coherence.shell_pid
    ), "the established shell must still be this pane's shell after the launch"
