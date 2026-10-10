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

**THE WORKSPACE ROOT NOW HAS THE SAME BOUNDED IDENTITY PREMISE (work-item
`overseer-2qjuho`).** The repair above deliberately covered the pane the writer
creates, but `_start_server` still returned the workspace root's FIRST process
reading immediately after `workspace.create`. Three later full-suite receipts
showed that first reading reporting `'herdr'` while the kernel already reported
`/usr/bin/bash` or `/usr/bin/dash`; `_assert_alias_context` then accused the host
premise before the public writer ran. The root is now returned only after the
shared exact-pane wait observes an available, coherent server/kernel identity
within the existing readiness bound. Its last observation is named on expiry.

The controls disclose their fault injection rather than relabelling it as a
historical reproduction: one initial unusable or deliberately contradictory
reply is followed by real native readings from the owned server, while a
persistently unusable reply drives a deterministic bounded refusal. The latter
also proves that setup failure removes exactly its own Herdr server and session
while an unrelated owned session remains reachable.

Session isolation is herdr's own `--session` mechanism: every session name
carries this test process's pid, and teardown stops and deletes BY THAT EXACT
NAME, so no other session — including the operator's `default` — is touched.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import claude_sessions
import herdr_alias_fixture_identity
import herdr_identity
import herdr_protocol
import herdr_transport
import herdr_write
import pytest
from herdr_alias_fixture_identity import (
    alias_session_name,
    herdr_api_socket_path,
    herdr_client_socket_path,
    unix_socket_path_capacity,
)
from herdr_listener_readiness import (
    ListenerPoll,
    ListenerProbe,
    ListenerReadiness,
    await_owned_listener,
    owned_listener_peer_pid,
)
from test_herdr_live_observations import (
    TRANSIENT_NAME,
    TRANSIENT_SECONDS,
    BoundedPoll,
    ForegroundReading,
    PaneIdentity,
    ReadyShellGate,
    RegisteredShell,
    ShellRecovery,
    await_coherent_identity,
    await_occupying_child,
    kernel_executable_of,
    leader_name,
    parent_pid_of,
    process_info_reply,
    raw_request,
    read_foreground,
    registered_login_shells,
    startup_transient,
)

__all__: list[str] = []

HERDR_BINARY = "herdr"
SERVER_READY_TIMEOUT = 30.0
LAUNCH_TIMEOUT = 20.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
LOGIN_SHELL_REGISTRY = "/etc/shells"
HERDR_SESSION_NAME_BYTES = 64

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
    listener_readiness: ListenerReadiness


def _socket_for(*, session: str) -> Path:
    return herdr_api_socket_path(session=session)


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
    registered: tuple[RegisteredShell, ...]
    seconds: float = READY_SECONDS
    coherence_seconds: float = READY_SECONDS
    # Real, OWNED unavailability, for the control below: the fixture closes the
    # pane it is about to establish, so the server genuinely has no reading to
    # give for it. Never set by an exercise.
    close_before_establishing: bool = False
    panes: list[str] = field(default_factory=list)
    gate: ReadyShellGate | None = None
    coherence: PaneIdentity | None = None
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
            self.coherence = await_coherent_identity(
                read=lambda: process_info_reply(socket_path=self.socket_path, pane_id=pane_id),
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


def _start_server(
    *,
    session: str,
    scratch: Path,
    shell_path: str | None,
    root_poll: BoundedPoll | None = None,
    listener_poll: ListenerPoll | None = None,
    listener_probe: ListenerProbe = owned_listener_peer_pid,
) -> LiveServer:
    """A server whose panes are rooted at `shell_path`, or at herdr's own fallback.

    The environment is built EXPLICITLY — `$SHELL` removed rather than merely
    left alone — because the whole subject of this file is which shell the pane
    comes up as, and inheriting the ambient value would make that the operator's
    choice rather than the test's.

    The identity established here is the ROOT pane's, which is what the host's
    alias premise is asserted against. An unusable, occupied or contradictory
    first reading is consumed within the same bounded exact-pane wait used for
    created panes; only a coherent server/kernel identity is returned. This says
    nothing about the pane an exercise writes into: that one is established by
    :class:`_Readiness`.
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
    try:
        listener_readiness = await_owned_listener(
            socket_path=address,
            session=session,
            child=child,
            poll=listener_poll or ListenerPoll(seconds=SERVER_READY_TIMEOUT),
            probe=listener_probe,
        )
    except AssertionError as failed:
        listener_failure: AssertionError | None = failed
    else:
        listener_failure = None
    finally:
        log.close()
    if listener_failure is not None:
        raise AssertionError(
            f"{listener_failure}; server log: "
            f"{(scratch / log_name).read_text(errors='replace')[:500]}"
        ) from listener_failure
    created = raw_request(
        socket_path=str(address),
        method="workspace.create",
        params={"cwd": PANE_CWD, "label": session, "focus": False},
    )
    assert "result" in created, f"workspace.create failed: {created}"
    root = str(created["result"]["root_pane"]["pane_id"])
    identity = await_coherent_identity(
        read=lambda: process_info_reply(socket_path=str(address), pane_id=root),
        pane_id=root,
        poll=root_poll or BoundedPoll(seconds=READY_SECONDS),
        registered=registered_login_shells(),
    )
    assert (
        identity.coherent is True
    ), f"workspace root {root!r} readiness was not established: {identity.reason}"
    return LiveServer(
        session=session,
        socket_path=str(address),
        server_pid=child.pid,
        root=root,
        reported_name=identity.reported,
        kernel_executable=identity.executable,
        listener_readiness=listener_readiness,
    )


def _serve(
    *,
    scratch: Path,
    session: str,
    shell_path: str | None,
    root_poll: BoundedPoll | None = None,
    listener_poll: ListenerPoll | None = None,
    listener_probe: ListenerProbe = owned_listener_peer_pid,
) -> Iterator[LiveServer]:
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    try:
        server = _start_server(
            session=session,
            scratch=scratch,
            shell_path=shell_path,
            root_poll=root_poll,
            listener_poll=listener_poll,
            listener_probe=listener_probe,
        )
        yield server
    finally:
        _ = _cli(args=["--session", session, "server", "stop"])
        _ = _cli(args=["session", "delete", session])


@pytest.fixture(name="alias_server")
def _alias_server(*, tmp_path: Path) -> Iterator[LiveServer]:
    """A server with NO `$SHELL`, so herdr roots its panes at `/bin/sh`."""
    yield from _serve(scratch=tmp_path, session=alias_session_name(label="sh"), shell_path=None)


@pytest.fixture(name="exact_server")
def _exact_server(*, tmp_path: Path) -> Iterator[LiveServer]:
    """A server with `SHELL=/bin/bash`, whose reported name needs no alias."""
    yield from _serve(
        scratch=tmp_path, session=alias_session_name(label="bash"), shell_path="/bin/bash"
    )


@dataclass(kw_only=True)
class _ControlledServerChild:
    """A deterministic running child for the pre-request listener wait."""

    pid: int
    status: int | None = None

    def poll(self) -> int | None:
        return self.status


def test_owned_listener_probe_connects_without_transmitting(*, tmp_path: Path) -> None:
    """The real readiness probe observes this process and sends no request bytes."""
    address = tmp_path / "accepting.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(address))
        listener.listen()

        peer_pid = owned_listener_peer_pid(socket_path=str(address), expected_pid=os.getpid())
        connection, _peer_address = listener.accept()
        with connection:
            connection.settimeout(0.1)
            transmitted = connection.recv(1)

    assert peer_pid == os.getpid()
    assert transmitted == b"", "the readiness probe must close without transmitting a request"


def test_listener_wait_bounds_a_live_child_that_never_publishes_a_socket(*, tmp_path: Path) -> None:
    """A missing pathname consumes the same deadline without attempting a request."""
    address = tmp_path / "never-published.sock"
    child = _ControlledServerChild(pid=6891)
    clock = iter([0.0, 0.0, 1.0])
    events: list[str] = []

    def unexpected_probe(*, socket_path: str, expected_pid: int) -> int:
        events.append(f"probe:{socket_path}:{expected_pid}")
        return child.pid

    with pytest.raises(AssertionError) as refused:
        _ = await_owned_listener(
            socket_path=address,
            session="controlled missing pathname",
            child=child,
            poll=ListenerPoll(
                seconds=1.0,
                monotonic=lambda: next(clock, 1e9),
                sleep=lambda _seconds: events.append("sleep"),
            ),
            probe=unexpected_probe,
        )

    message = str(refused.value)
    assert "did not expose a connectable owned listener" in message
    assert f"socket path {address} does not exist" in message
    assert "within 1.0s after 0 connect attempts" in message
    assert events == ["sleep"], "a missing pathname must not reach the transport probe"


def test_listener_wait_consumes_path_before_listen_refusal_before_workspace_creation(
    *, tmp_path: Path
) -> None:
    """Controlled timing: pathname publication precedes listener acceptance.

    This is not presented as a reproduction of Herdr's startup timing. The
    injected probe reports one connection refusal after the pathname exists,
    then reports the owned pid. Only after that discriminator returns does this
    test model the fixture's one ``workspace.create`` transmission.
    """
    address = tmp_path / "herdr.sock"
    address.touch()
    child = _ControlledServerChild(pid=4173)
    events: list[str] = []

    def path_before_listener(*, socket_path: str, expected_pid: int) -> int:
        assert Path(socket_path).is_socket() is False
        assert Path(socket_path).exists() is True
        assert expected_pid == child.pid
        if not events:
            events.append("listener-refused")
            raise ConnectionRefusedError("controlled path-before-listen refusal")
        if len(events) == 1:
            events.append("listener-unowned")
            return child.pid + 1
        events.append("listener-owned")
        return child.pid

    observed = await_owned_listener(
        socket_path=address,
        session="controlled-alias",
        child=child,
        poll=ListenerPoll(seconds=SERVER_READY_TIMEOUT, sleep=lambda _seconds: None),
        probe=path_before_listener,
    )
    events.append("workspace.create")

    assert events == [
        "listener-refused",
        "listener-unowned",
        "listener-owned",
        "workspace.create",
    ], events
    assert observed.attempts == 3
    assert observed.peer_pid == child.pid


@pytest.mark.parametrize(
    ("phase", "ticks"),
    [("during listener polling", [0.0, 0.0]), ("at the listener deadline", [0.0, 1.0])],
)
def test_owned_server_exit_during_listener_readiness_is_not_reported_as_a_timeout(
    *, tmp_path: Path, phase: str, ticks: list[float]
) -> None:
    """Each child observation boundary wins over a generic timeout diagnostic."""
    address = tmp_path / "deadline.sock"
    child = _ControlledServerChild(pid=5219, status=23)
    clock = iter(ticks)

    with pytest.raises(AssertionError) as refused:
        _ = await_owned_listener(
            socket_path=address,
            session=f"controlled exit {phase}",
            child=child,
            poll=ListenerPoll(
                seconds=1.0,
                monotonic=lambda: next(clock, 1e9),
                sleep=lambda _seconds: None,
            ),
            probe=owned_listener_peer_pid,
        )

    message = str(refused.value)
    assert "owned server process 5219 exited with status 23" in message


@dataclass(frozen=True, kw_only=True)
class _ListenerFailureReceipt:
    """The diagnostic and ownership observations from one refused setup."""

    message: str
    attempts: int
    target_session: str
    target_removed: bool
    peer_usable: bool


@dataclass(kw_only=True)
class _ListenerFailureClock:
    """Keep deadline establishment separate from readiness observations."""

    address: Path
    ticks: Iterator[float] = field(default_factory=lambda: iter([0.0, 1.0, 3.0]))
    deadline_pending: bool = True

    def __call__(self) -> float:
        if self.deadline_pending:
            self.deadline_pending = False
            return 0.0
        return next(self.ticks, 1e9) if self.address.exists() else 0.0


def _exercise_listener_failure(*, tmp_path: Path, failure: str) -> _ListenerFailureReceipt:
    """Drive one controlled listener failure against an unrelated live peer."""
    peer_scratch = tmp_path / "peer"
    target_scratch = tmp_path / "target"
    peer_scratch.mkdir()
    target_scratch.mkdir()
    peer = _serve(
        scratch=peer_scratch,
        session=alias_session_name(label=f"listener-peer-{failure}"),
        shell_path="/bin/bash",
    )
    peer_server = next(peer)
    target_label = f"listener-{failure}"
    target_session = alias_session_name(label=target_label)
    target_address = _socket_for(session=target_session)
    controlled_clock = _ListenerFailureClock(address=target_address)
    attempts = [0]

    def controlled_refusal(*, socket_path: str, expected_pid: int) -> int:
        attempts[0] += 1
        assert Path(socket_path).exists(), "the refusal is after pathname publication"
        if failure == "exited" and attempts[0] == 1:
            os.kill(expected_pid, signal.SIGTERM)
            time.sleep(0.05)
        raise ConnectionRefusedError(f"controlled {failure} listener refusal")

    target = _serve(
        scratch=target_scratch,
        session=target_session,
        shell_path=None,
        listener_poll=ListenerPoll(
            seconds=2.0,
            monotonic=controlled_clock,
            sleep=lambda _seconds: time.sleep(0.01),
        ),
        listener_probe=controlled_refusal,
    )
    try:
        with pytest.raises(AssertionError) as refused:
            _ = next(target)
        return _ListenerFailureReceipt(
            message=str(refused.value),
            attempts=attempts[0],
            target_session=target_session,
            target_removed=not target_address.parent.exists(),
            peer_usable=peer_server.root in _pane_ids(socket_path=peer_server.socket_path),
        )
    finally:
        target.close()
        peer.close()


@pytest.mark.parametrize("failure", ["exited", "never-accepting"])
def test_listener_setup_failure_is_bounded_and_cleans_only_its_owned_session(
    *, tmp_path: Path, failure: str
) -> None:
    """Exit and non-acceptance are named; cleanup cannot cross session ownership.

    Both faults are controlled fixture validation, not claims about the reported
    host race. The exit leg terminates the exact spawned child during its first
    connect probe. The never-accepting leg keeps the real server live but makes
    this fixture's injected transport probe report refusal through the complete
    deterministic startup bound.
    """
    receipt = _exercise_listener_failure(tmp_path=tmp_path, failure=failure)

    assert f"herdr session {receipt.target_session!r}" in receipt.message, receipt.message
    assert "server log:" in receipt.message, receipt.message
    if failure == "exited":
        assert "owned server process" in receipt.message, receipt.message
        assert "exited with status -15" in receipt.message, receipt.message
        assert receipt.attempts == 1, "exit detection must stop further connect probes"
    else:
        assert "did not expose a connectable owned listener" in receipt.message, receipt.message
        assert "within 2.0s" in receipt.message, receipt.message
        assert (
            "ConnectionRefusedError: controlled never-accepting listener refusal" in receipt.message
        )
        assert receipt.attempts == 2, "the deterministic bound permits exactly two probes"
    assert (
        receipt.target_removed
    ), f"the refused setup left its owned session {receipt.target_session!r} registered"
    assert receipt.peer_usable, "cleanup crossed into the unrelated owned Herdr session"


RawRequest = Callable[..., dict[str, Any]]


@dataclass(kw_only=True)
class _DelayedListenerSetup:
    """One disclosed pre-listen refusal and the ordered setup effects."""

    actual_request: RawRequest
    probe_calls: int = 0
    events: list[str] = field(default_factory=list)

    def listener_probe(self, *, socket_path: str, expected_pid: int) -> int:
        self.probe_calls += 1
        assert Path(socket_path).exists(), "the controlled refusal follows pathname publication"
        if self.probe_calls == 1:
            self.events.append("listener-refused")
            raise ConnectionRefusedError("controlled native path-before-listen refusal")
        peer_pid = owned_listener_peer_pid(socket_path=socket_path, expected_pid=expected_pid)
        self.events.append("listener-owned")
        return peer_pid

    def request(
        self, *, socket_path: str, method: str, params: dict[str, object]
    ) -> dict[str, Any]:
        if method == "workspace.create":
            self.events.append(method)
            assert self.events == ["listener-refused", "listener-owned", "workspace.create"], (
                "workspace.create reached the real transport before the fixture established "
                f"owned-listener readiness: {self.events}"
            )
        return self.actual_request(socket_path=socket_path, method=method, params=params)


def _legacy_socket_boundary(*, description: str) -> tuple[str, str]:
    """A descriptive label whose former pid-prefixed identity filled Herdr's limit."""
    legacy_prefix = f"overseer-test-{os.getpid()}-alias-"
    padding = HERDR_SESSION_NAME_BYTES - len(os.fsencode(legacy_prefix + description))
    assert padding > 0, "the disclosed description must fit Herdr's session-name boundary"
    label = f"{description}{'x' * padding}"
    session = f"{legacy_prefix}{label}"
    assert len(os.fsencode(session)) == HERDR_SESSION_NAME_BYTES
    return label, session


def _assert_session_path_is_bounded(*, session: str, legacy_session: str) -> None:
    """The owned identity fits the actual native budget that the legacy path exceeds."""
    socket_capacity = unix_socket_path_capacity()
    legacy_client_socket = herdr_client_socket_path(session=legacy_session)
    bounded_client_socket = herdr_client_socket_path(session=session)
    assert len(os.fsencode(legacy_client_socket)) >= socket_capacity, (
        legacy_client_socket,
        socket_capacity,
    )
    assert len(os.fsencode(bounded_client_socket)) < socket_capacity, (
        bounded_client_socket,
        socket_capacity,
    )
    assert session != legacy_session


def test_client_socket_path_reuses_public_api_path(*, monkeypatch: pytest.MonkeyPatch) -> None:
    """The longer client socket retains the public API socket's registry parent."""
    api_path = Path("/fixture-registry/owned/herdr.sock")
    observed_sessions: list[str] = []

    def api_socket_path(*, session: str) -> Path:
        observed_sessions.append(session)
        return api_path

    monkeypatch.setattr(herdr_alias_fixture_identity, "herdr_api_socket_path", api_socket_path)

    client_path = herdr_alias_fixture_identity.herdr_client_socket_path(session="owned")

    assert client_path == api_path.with_name("herdr-client.sock")
    assert observed_sessions == ["owned"]


@pytest.mark.parametrize(
    ("shell_path", "identity_kind"), [(None, "registered alias"), ("/bin/bash", "exact name")]
)
def test_listener_recovery_preserves_one_workspace_and_native_shell_guards(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shell_path: str | None,
    identity_kind: str,
) -> None:
    """Recovered listener setup retains both native shell authorization paths."""
    description = f"listener-native-{identity_kind.replace(' ', '-')}"
    label, legacy_session = _legacy_socket_boundary(description=description)
    setup = _DelayedListenerSetup(actual_request=raw_request)
    monkeypatch.setattr(f"{__name__}.raw_request", setup.request)
    served = _serve(
        scratch=tmp_path,
        session=alias_session_name(label=label),
        shell_path=shell_path,
        listener_probe=setup.listener_probe,
    )
    try:
        server = next(served)
        listener = getattr(server, "listener_readiness", None)
        assert isinstance(
            listener, ListenerReadiness
        ), "successful setup must retain its owned-listener observation for native proof"
        assert listener.attempts == 2 and listener.peer_pid == server.server_pid, listener
        assert setup.events == [
            "listener-refused",
            "listener-owned",
            "workspace.create",
        ], setup.events
        _assert_session_path_is_bounded(session=server.session, legacy_session=legacy_session)
        readiness = _readiness_for(server=server, scratch=tmp_path)
        outcome, coherence = _graded_launch(server=server, readiness=readiness)
        assert outcome.ok is True, outcome.error
        if shell_path is None:
            mediating = _assert_alias_context(server=server)
            assert coherence.mediated_by == mediating.declared, coherence
        else:
            assert server.reported_name == Path(server.kernel_executable).name, server
            assert coherence.mediated_by == "", coherence
        _ = _observe_launched_child(
            socket_path=server.socket_path,
            pane_id=outcome.pane_id,
            shell_pid=coherence.shell_pid,
        )
        assert readiness.writer_deliveries() == [(outcome.pane_id, LAUNCH_COMMAND, ("Enter",))]
    finally:
        served.close()


def _scratch_pair(*, root: Path) -> tuple[Path, Path]:
    """Two directories for live servers that must coexist."""
    peer = root / "peer"
    target = root / "target"
    peer.mkdir()
    target.mkdir()
    return peer, target


def test_concurrent_alias_fixtures_have_distinct_sessions_and_exact_cleanup(
    *, tmp_path: Path
) -> None:
    """Closing one same-label fixture leaves its peer identity answering requests."""
    peer_scratch, target_scratch = _scratch_pair(root=tmp_path)
    label, _legacy_session = _legacy_socket_boundary(description="concurrent-native-peer")
    peer_session = alias_session_name(label=label)
    target_session = alias_session_name(label=label)
    assert peer_session != target_session, "concurrent fixture instances need distinct ownership"
    peer = _serve(scratch=peer_scratch, session=peer_session, shell_path="/bin/bash")
    target = _serve(scratch=target_scratch, session=target_session, shell_path="/bin/bash")
    try:
        peer_server = next(peer)
        try:
            target_server = next(target)
            assert target_server.session == target_session
            assert target_server.root in _pane_ids(socket_path=target_server.socket_path)
            target_address = _socket_for(session=target_session)
            assert target_address.is_socket()
        finally:
            target.close()

        peer_pid_before = owned_listener_peer_pid(
            socket_path=peer_server.socket_path, expected_pid=peer_server.server_pid
        )
        fresh_panes = _pane_ids(socket_path=peer_server.socket_path)
        peer_pid_after = owned_listener_peer_pid(
            socket_path=peer_server.socket_path, expected_pid=peer_server.server_pid
        )
        assert not target_address.parent.exists(), target_address
        assert peer_server.session == peer_session
        assert peer_server.root in fresh_panes
        assert peer_pid_before == peer_pid_after == peer_server.server_pid
    finally:
        peer.close()


def _readiness_for(*, server: LiveServer, scratch: Path, **overrides: Any) -> _Readiness:
    """One establishment's worth of state, with the host's real register read fresh."""
    return _Readiness(
        socket_path=server.socket_path,
        transient=startup_transient(scratch=scratch),
        registered=registered_login_shells(),
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


def _assert_established(*, readiness: _Readiness, pane_id: str) -> PaneIdentity:
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
) -> tuple[Any, PaneIdentity]:
    """Run the public facade, then GRADE the fixture premise before returning an outcome.

    The ORDER is what
    `test_unavailable_or_expired_readiness_fails_before_alias_authorization_is_graded`
    is about: no caller can reach an assertion about alias authorization without
    the created pane's readiness having been established first, because the
    grading happens HERE rather than in each test.
    """
    outcome = _split_top(server=server, readiness=readiness, command=command, **overrides)
    return outcome, _assert_established(readiness=readiness, pane_id=outcome.pane_id)


def _assert_alias_context(*, server: LiveServer) -> RegisteredShell:
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
    registered = registered_login_shells()
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


def _assert_alias_denial(*, outcome: Any, coherence: PaneIdentity, readiness: _Readiness) -> None:
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


def _frozen_poll(*, seconds: float, ticks: list[float]) -> BoundedPoll:
    """A deterministic bound whose clock advances only through `ticks`."""
    remaining = list(ticks)

    def monotonic() -> float:
        return remaining.pop(0) if remaining else 1e9

    return BoundedPoll(seconds=seconds, monotonic=monotonic, sleep=lambda _seconds: None)


@pytest.mark.parametrize(
    ("fault", "shell_path"),
    [("unavailable", None), ("incoherent", "/bin/bash")],
)
def test_workspace_root_setup_consumes_one_controlled_fault_before_native_coherence(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    shell_path: str | None,
) -> None:
    """One disclosed bad sample is consumed before the real root identity is returned.

    This is controlled fixture validation, not a reproduction of the host race.
    The first reply is either deliberately unusable or made contradictory by
    renaming its real foreground leader; every later reply comes unchanged from
    the owned native server.
    """
    actual_process_info = process_info_reply
    reads = 0

    def one_fault_then_native(*, socket_path: str, pane_id: str) -> dict[str, Any]:
        nonlocal reads
        reads += 1
        reply = actual_process_info(socket_path=socket_path, pane_id=pane_id)
        if reads != 1:
            return reply
        reading = read_foreground(reply=reply)
        assert reading is not None, "the controlled fault needs one real native reading to alter"
        if fault == "unavailable":
            return {
                "result": {
                    "process_info": {
                        "pane_id": pane_id,
                        "shell_pid": reading.shell_pid,
                    }
                }
            }
        assert fault == "incoherent", fault
        return {
            "result": {
                "process_info": {
                    "pane_id": pane_id,
                    "shell_pid": reading.shell_pid,
                    "foreground_process_group_id": reading.group_id,
                    "foreground_processes": [
                        {
                            "pid": pid,
                            "name": "herdr" if pid == reading.group_id else name,
                            "cmdline": name,
                            "cwd": PANE_CWD,
                        }
                        for pid, name in reading.processes
                    ],
                }
            }
        }

    monkeypatch.setattr(f"{__name__}.process_info_reply", one_fault_then_native)
    scratch = tmp_path / fault
    scratch.mkdir()
    served = _serve(
        scratch=scratch,
        session=alias_session_name(label=f"root-{fault}"),
        shell_path=shell_path,
    )
    try:
        server = next(served)
        native = _reading(socket_path=server.socket_path, pane_id=server.root)
        executable = kernel_executable_of(pid=native.shell_pid)

        assert reads >= 2, "the controlled first fault must be consumed before setup returns"
        assert server.reported_name == leader_name(reading=native)
        assert executable is not None and server.kernel_executable == executable
        if shell_path is None:
            _ = _assert_alias_context(server=server)
        else:
            assert server.reported_name == Path(server.kernel_executable).name
    finally:
        served.close()


def test_persistently_unavailable_root_setup_is_bounded_and_cleans_only_its_session(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A named root refusal removes its session while an owned peer remains live."""
    peer_scratch = tmp_path / "peer"
    target_scratch = tmp_path / "target"
    peer_scratch.mkdir()
    target_scratch.mkdir()
    peer = _serve(
        scratch=peer_scratch,
        session=alias_session_name(label="root-peer"),
        shell_path="/bin/bash",
    )
    peer_server = next(peer)

    def unavailable(*, socket_path: str, pane_id: str) -> dict[str, Any]:
        del socket_path
        return {"result": {"process_info": {"pane_id": pane_id}}}

    monkeypatch.setattr(f"{__name__}.process_info_reply", unavailable)
    target_label = "root-refusal"
    target_session = alias_session_name(label=target_label)
    target = _serve(
        scratch=target_scratch,
        session=target_session,
        shell_path=None,
        root_poll=_frozen_poll(seconds=2.0, ticks=[0.0, 1.0, 3.0]),
    )
    try:
        with pytest.raises(AssertionError) as refused:
            _ = next(target)

        message = str(refused.value)
        assert "never reported a coherent shell identity within 2.0s" in message, message
        assert "no usable shell/foreground fields" in message, message
        assert not _socket_for(
            session=target_session
        ).parent.exists(), f"the refused setup left its owned session {target_session!r} registered"
        assert peer_server.root in _pane_ids(
            socket_path=peer_server.socket_path
        ), "setup cleanup crossed into the unrelated owned Herdr session"
    finally:
        target.close()
        peer.close()


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
