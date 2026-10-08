"""A REAL foreground child in the new pane withholds the launch, against live herdr.

The native counterpart of `tests/test_herdr_layout_launch_authorization.py`.
That file stages every unreadable, ambiguous and foreign process reading a
healthy server will not produce on demand; this one stages the single condition
that matters most and that only a real terminal can produce honestly — a
genuine process occupying the newly created pane's foreground at the moment the
daemon command would be written into it.

**The fault injection, stated plainly.** The writer is the SHIPPED
`HerdrWriter`, entered through its own public `split_window_top`, with its PUBLIC
`request` seam interposed by the shared `ReadyWriter`. Every request it makes goes
to the REAL `herdr --session <unique> server`, unchanged. The fixture does exactly
two things at that seam, at two different points in the writer's own sequence:

  - before the FIRST `pane.process_info` naming the created pane, and only the
    first, it establishes that pane's INITIAL readiness — available and coherent;
  - after the `pane.layout` request returns, it runs `sleep 300` in that same pane
    over its own separate connection to the real server and OBSERVES that child.

`pane.layout` sits between the writer's two readings, so by the time the adapter
takes its pre-launch RECHECK the pane is occupied by a real child of a real shell,
and the reading proving it comes from herdr rather than from the surface under test.

**THE OCCUPANT ARRIVES AFTER INITIAL READINESS, AND THAT ORDERING IS THE POINT.**
The establishment is one-shot, so the reading that meets the occupant has no
establishment and no waiting behind it: the fixture cannot wait the occupant away.
An exercise whose fixture kept re-establishing would quietly turn this proof into
its opposite — it would wait until the pane was idle again and then observe a
launch succeeding.

**THIS FILE NO LONGER OWNS A FORWARDING PROXY, and that is a repair rather than a
simplification.** The predecessor pointed the writer at an AF_UNIX proxy this test
process owned and injected at the proxy, which made the peer the writer VALIDATED
this test process instead of the real herdr server — a real generation check against
a real process, but not against the server the exercise is about. It also put the
establishment INSIDE one request's single absolute transport deadline, which forced
the gate's bounds to be sized against that deadline, and it needed a relay thread
that had to survive an idle `accept` (a `socket.timeout` is an `OSError`, so the
original `except OSError: return` killed the relay mid-sequence). All three of those
costs are gone: the target names the REAL server's pid and `/proc` start time, the
establishment completes before `super().request` hands anything to
`herdr_transport`, and there is no thread to keep alive.

**What "OBSERVES that child" has to mean, because this fixture used to get it
wrong and ACCUSE THE PRODUCT OF ITS OWN DEFECT.** The old wait returned as soon
as the pane's `foreground_process_group_id` differed from its `shell_pid` — any
difference, by any process. Measured on the operator host: shell `zsh` 3584980,
then foreground 3585294 named `mv`, a child of that shell's own startup. The
wait returned before `sleep` had ever run and stamped its precondition flag
anyway, so the pane the adapter read was genuinely IDLE and it returned
`outcome.ok=True` — correctly. `assert outcome.ok is False` therefore **FAILED**,
and the recurrence was recorded as a failing expected-refusal test.

**That direction is the whole point, and the opposite reading is the tempting
one.** This was a FAILING test against a CORRECT product, never a passing test
concealing a defect. Because no occupant was ever staged, the run carries NO
evidence either way about whether the adapter would accept a PROVEN occupied
pane — the question the exercise exists to ask was simply never put. A false
fixture premise produced a false accusation, and the repair's value is that the
same premise now fails as a FIXTURE failure that names what it saw.

Two sibling defects came out of the same loop: one real run raised
`KeyError: 'foreground_process_group_id'` inside the setup thread, and the loop
returned silently at its deadline, so a setup TIMEOUT and an established
precondition were the same return value.

**THE INTENDED INJECTION WAS NOT EVEN REACHABLE UNTIL THE CREATED PANE'S INITIAL
READINESS WAS ESTABLISHED (work-item `overseer-hottfz`).** The adapter reads the
created pane's process info TWICE — once to ESTABLISH its retained shell right
after the pane is proven, and once to RECHECK that shell immediately before the
write — and the `pane.layout` request this fixture injects at falls BETWEEN them.
So a created pane that is already busy at the FIRST reading refuses one guard
before the swap, the sequence never asks for a layout, and the occupant this
exercise exists to stage is never injected at all. Measured on the operator host:
`occupation` was None, the proxy had seen
`['pane.list', 'pane.split', 'pane.list', 'pane.process_info']` with `created` at
`w1:p3`, and the exercise failed on its own fixture premise.

That premise was then demonstrated deliberately in the factory sandbox BEFORE
that repair, rather than inferred from the guard ordering. With one real
`sleep 300` observed owning the created pane `w1:p3` (child 5383 under retained
shell 5376, foreground group 5383) at the request immediately before the adapter's
first reading, the shipped exercise relayed exactly
`['pane.list', 'pane.split', 'pane.list', 'pane.process_info']` — no `pane.swap`,
no `pane.layout`, `occupation` still None — the adapter refused with
`'w1:p3' is OCCUPIED: foreground group 5383 is not its retained shell 5376`, and
the occupant check failed by name with "the fixture's occupation step never
completed". Same pane id and same method list as the host receipt.

**That demonstration's PROVENANCE is weaker than its content, and the gap is
recorded rather than papered over.** Those are real readings printed by a real
pytest process driving the then-unmodified file, but the command was piped into
`tail`, so the producer's own exit status was never captured — the shell reported
the pipeline, not the run. The observations stand on their own printed values; no
pytest PASS/FAIL verdict is claimed for that command.

**A FOURTH premise was missing and is now established too (work-item
`overseer-3zfpz5`): the created pane's own shell IDENTITY.** Availability — the
pane's shell owns an idle foreground — is not the same fact as coherence, and a
sibling exercise measured a created pane reporting its shell as `'herdr'` while the
kernel ran `/usr/bin/bash`, which the product refused and the fixture had never
looked at. The establishment here is therefore two bounded observations, and
`_established` grades both before anything grades the adapter.

The staged initial child is the weaker claim deliberately: a bounded
DISCRIMINATING instance of a non-idle created pane, not a reproduction of the
operator's `zsh`/`mise`/`atuin` startup. On a shell that loads nothing — which this
sandbox's declared minimal `dash` certainly is — the exercises here passed before
these repairs and pass after them, as PRESERVATION controls over guards that
already hold, and none of it is a product Red.

**Every request the fixture makes goes to the real socket on its OWN raw
connection**, so the fixture's setup input never enters `readiness.deliveries()`
and the zero-delivery claim describes the WRITER's stream alone. Every control fact
is read from the real server over a raw socket too, never from the adapter's
account: the geometry that shows the created pane really did end up above the
original, the process reading that shows the occupying child is still alive
afterwards, and the three pane captures that show the command text reached none of
them.

**The server's own shell is a DECLARED fixture choice, not an inherited one.**
`start_owned_server` gives it a private herdr config selecting an available,
registered minimal shell in `non_login` mode and excludes the one interactive
startup hook `non_login` does not close, while preserving the rest of the parent
environment; see `tests/test_herdr_live_observations.py`.

**ONE MORE SEAM CLAIMED A BOUNDED OBSERVATION AND DID NOT MAKE ONE, and it is
repaired separately from all of the above.** `_await_named` polls for the first
reading in which a pane lists a named foreground process, and it took those
readings through the single-shot `_reading`, whose `assert` turned ONE unusable
reply into the end of the exercise. Separately observed on the host as
`run_in_pane` (transient) then `_await_named` then `_reading` asserting None, it
never entered the layout adapter. That is POST-COMMAND child observation — not
the initial readiness above, and not a production guard — so the repair is
confined to that loop: tolerate an unusable reading within the SAME bound,
report the last reason at expiry, and leave `_reading` asserting for the
single-shot callers it belongs to. The scripted controls at the foot of this
file put that question; the native `test_a_real_transient_is_not_mistaken_for_
the_requested_occupant` above is its real-transient pair. The controlled
unavailability is a DISCLOSED fault control and claims no reproduction of the
historical host timing, whose origin remains unknown.

Session isolation is herdr's own `--session` mechanism: the name carries this
test process's pid, and teardown stops and deletes BY THAT EXACT NAME, so no
other session — including the operator's `default` — is touched.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_sessions
import herdr_identity
import herdr_write
import pytest
from test_herdr_live_observations import (
    POLL_SECONDS,
    TRANSIENT_NAME,
    TRANSIENT_SECONDS,
    BoundedPoll,
    ChildObservation,
    ForegroundReading,
    PaneIdentity,
    PaneReadiness,
    ReadyWriter,
    ShellIdentityPin,
    await_idle_shell,
    await_occupying_child,
    occupying_child_pid,
    pane_capture,
    parent_pid_of,
    process_info_reply,
    raw_request,
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

OCCUPY_TIMEOUT = 20.0
# The writer's own per-request ceiling. Unlike the predecessor's, this is NOT
# coupled to the establishment's bound: the establishment completes before
# `super().request` hands anything to `herdr_transport`, so nothing is racing a
# transport timeout and the shared default bound needs no narrowing.
WRITER_TIMEOUT = 30.0
PANE_CWD = "/tmp"
TOP_RATIO = 0.25
# The writer request after which the LATE occupant is staged. It sits between the
# writer's establish reading and its pre-launch recheck, which is what makes the
# occupant arrive after initial readiness and meet the recheck.
OCCUPY_AFTER = "pane.layout"
# Long-lived and inert, so the occupied reading is stable while the assertions
# run; teardown stops the whole session, so nothing is left behind.
OCCUPYING_COMMAND = "sleep 300"
OCCUPYING_NAME = "sleep"
# Deliberately not a runnable command: if it ever reaches a pane, it is visible
# in that pane's capture as itself.
DAEMON_COMMAND = "DO_NOT_SEND_TO_AN_OCCUPIED_PANE"


@dataclass(frozen=True, kw_only=True)
class LiveTab:
    """One OWNED herdr server, the pane under supervision and an unrelated sibling."""

    socket_path: str
    server_pid: int
    original: str
    unrelated: str
    transient: str


def _reading(*, socket_path: str, pane_id: str) -> ForegroundReading:
    """`pane_id`'s live process reading, or an explicit FIXTURE failure.

    An unusable reply is a failed control read rather than a fact about the
    pane, so it stops the exercise here instead of raising a `KeyError` out of
    whichever assertion happened to touch the missing field first.
    """
    reading = read_foreground(reply=process_info_reply(socket_path=socket_path, pane_id=pane_id))
    assert reading is not None, f"herdr returned no usable process reading for {pane_id!r}"
    return reading


def _await_named(*, socket_path: str, pane_id: str, name: str) -> ForegroundReading:
    """The first reading in which `pane_id` lists a foreground process `name`.

    The READING is returned, not just a pid, so a control can interrogate one
    single point-in-time observation from several angles without a second round
    trip the subject could change under.

    **An unusable reading is tolerated WITHIN the existing bound, and the expiry
    REPORTS why it expired.** This wait used to take its readings through
    `_reading`, whose `assert` is right for the SINGLE-SHOT callers it belongs to
    and wrong inside a poll: one unavailable reply is a fact about the READING,
    not about the pane, and it ended the exercise a bounded wait had promised to
    look past — in the separately observed host failure, before the layout
    adapter had been entered at all. The shape here is now the shared
    `await_occupying_child`'s: tolerate, remember the last reason, look again
    until the bound, then fail naming both what was awaited and what the pane
    actually held.

    The bound is `OCCUPY_TIMEOUT` and the interval is the shared `POLL_SECONDS`,
    both unchanged; nothing here waits globally, and `_reading` still asserts for
    its own single-shot callers.
    """
    deadline = time.monotonic() + OCCUPY_TIMEOUT
    reason = "no process reading was taken before the deadline"
    while time.monotonic() < deadline:
        reading = read_foreground(
            reply=process_info_reply(socket_path=socket_path, pane_id=pane_id)
        )
        if reading is None:
            reason = "no reading carried usable shell/foreground fields"
        elif reading.pids_named(name=name):
            return reading
        else:
            reason = f"its foreground is {list(reading.processes)}"
        time.sleep(POLL_SECONDS)
    pytest.fail(
        f"{pane_id!r} never reported a foreground process named {name!r} within "
        f"{OCCUPY_TIMEOUT}s: {reason}"
    )


def _geometry(*, socket_path: str, pane_id: str) -> dict[str, int]:
    """Every pane's TOP row on the tab, read from the real server."""
    reply = raw_request(socket_path=socket_path, method="pane.layout", params={"pane_id": pane_id})
    return {
        str(pane["pane_id"]): int(pane["rect"]["y"]) for pane in reply["result"]["layout"]["panes"]
    }


@pytest.fixture(name="live")
def _live(*, tmp_path: Path) -> Iterator[LiveTab]:
    """An owned server with two existing panes, cleaned up by name whatever happens.

    The sibling split is enclosed in the same teardown as the server: it is the
    fixture's own resource from the moment the seam returned it, and a failure
    there used to leave a live server behind.
    """
    session = f"overseer-test-{os.getpid()}-occupied"
    try:
        owned = start_owned_server(session=session, scratch=tmp_path, cwd=PANE_CWD)
        # An unrelated sibling in its OWN column, so any input or reshuffle landing
        # there is unmistakable.
        unrelated = split_pane(
            socket_path=owned.socket_path,
            pane_id=owned.root,
            direction="right",
            cwd=PANE_CWD,
        )
        yield LiveTab(
            socket_path=owned.socket_path,
            server_pid=owned.server_pid,
            original=owned.root,
            unrelated=unrelated,
            transient=startup_transient(scratch=tmp_path),
        )
    finally:
        stop_owned_server(session=session)


def _occupy_late(*, socket_path: str) -> Any:
    """Build the LATE fixture step: run a real child in the pane and OBSERVE it.

    Returns the observation rather than stamping a flag, so a caller cannot read a
    transient startup process, an unusable reading or an expired deadline as an
    established occupation. See this module's docstring for the three measured ways
    the predecessor did exactly that.

    Its traffic goes to the REAL socket on its own raw connection, so it never
    enters the writer's recorded request stream.
    """

    def occupy(*, pane_id: str) -> ChildObservation:
        run_in_pane(socket_path=socket_path, pane_id=pane_id, command=OCCUPYING_COMMAND)
        return await_occupying_child(
            read=lambda: process_info_reply(socket_path=socket_path, pane_id=pane_id),
            name=OCCUPYING_NAME,
            poll=BoundedPoll(seconds=OCCUPY_TIMEOUT),
        )

    return occupy


def _split_top(*, live: LiveTab) -> tuple[Any, PaneReadiness]:
    """The writer's own PUBLIC entrypoint, unchanged, against the REAL server.

    `HerdrWriter.split_window_top` is what this exercise is about, so it is what is
    called: the socket, the per-request deadline, the peer validation against the
    REAL server's pid and `/proc` start time, and the shell proof are all the shipped
    facade's. The inherited-facade assertion is what keeps that from being merely a
    claim — a fixture that had overridden it would fail here rather than quietly
    grading a different subject.
    """
    starttime = claude_sessions.proc_starttime(pid=live.server_pid)
    assert starttime is not None, "the live herdr server must have a readable start time"
    assert (
        ReadyWriter.split_window_top is herdr_write.HerdrWriter.split_window_top
    ), "the exercise must enter the SHIPPED public facade, not a fixture reimplementation"
    readiness = PaneReadiness(
        socket_path=live.socket_path,
        transient=live.transient,
        registered=registered_login_shells(),
        occupy_after=OCCUPY_AFTER,
        occupant=_occupy_late(socket_path=live.socket_path),
    )
    outcome = ReadyWriter(readiness=readiness, timeout_seconds=WRITER_TIMEOUT).split_window_top(
        target=herdr_identity.HerdrPaneTarget(
            socket_path=live.socket_path,
            server_pid=live.server_pid,
            server_starttime=starttime,
            pane_id=live.original,
        ),
        cwd=PANE_CWD,
        command=DAEMON_COMMAND,
        ratio=TOP_RATIO,
    )
    return outcome, readiness


def _established(*, readiness: PaneReadiness, pane_id: str) -> PaneIdentity:
    """Grade the INITIAL readiness premise before anything grades the adapter.

    Each fact separately so a failure says which one was missing: the step ran
    exactly ONCE and for the pane the writer created, the controlled child was
    observed under that pane's own pinned retained shell, it exited on its own, that
    same shell identity owns its foreground again, and the pane's server-reported
    name and kernel executable describe one program.

    The ONCE is the other half of the claim: the establishment ran before the
    writer's FIRST reading, and the writer's second reading — the one that meets the
    late occupant — was taken with nothing done to it. Both readings are asserted to
    have happened, because an exercise that stopped one guard early would otherwise
    read as a satisfied premise.
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
    assert gate.retained is not None, "the retained shell was never pinned as an identity"
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
        "the writer must still take BOTH of its readings — the established one and the "
        f"recheck that meets the occupant: {readiness.methods()}"
    )
    return identity


def _observed_occupant(*, readiness: PaneReadiness) -> int:
    """The pid of the child the fixture actually OBSERVED occupying the new pane.

    Every test below goes through this, so a fixture that failed to occupy the
    pane fails as a FIXTURE — naming what it saw instead — rather than being
    reported as a proof about the adapter's authorization.
    """
    occupation = readiness.occupation
    assert occupation is not None, (
        "the fixture's LATE occupation step never ran; the writer sent "
        f"{readiness.methods()} and readiness established {readiness.panes}"
    )
    assert occupation.pid is not None, f"the new pane was never occupied: {occupation.reason}"
    return occupation.pid


def test_a_really_occupied_new_pane_receives_no_command_or_enter_bytes(*, live: LiveTab):
    """THE native proof: a real child owns the new pane, so nothing is written to it.

    The writer must deliver no `pane.send_input` at all — that is the byte-level
    statement, and the keys are carried with it so an empty list means neither the
    command NOR its submission reached any pane — and the created pane's own capture
    must not contain the command text, which is the statement read from the terminal.

    The pane's INITIAL readiness is established first, so the refusal asserted here
    is the occupied-pane guard meeting the occupant this fixture staged AFTER that
    readiness — not the same guard meeting a pane that was busy before the swap was
    ever asked for, which is the measured shape that stopped the sequence one step
    early and never injected anything.
    """
    outcome, readiness = _split_top(live=live)

    identity = _established(readiness=readiness, pane_id=outcome.pane_id)
    child = _observed_occupant(readiness=readiness)
    gate = readiness.gate
    assert gate is not None and gate.transient is not None
    assert child != gate.transient.pid, (
        f"the occupant {child} is the readiness step's own bounded child {gate.transient}, not "
        "the distinct occupant this exercise staged after the layout read"
    )
    assert readiness.methods().count(OCCUPY_AFTER) == 1, (
        "the one-shot readiness step must not have swallowed the later occupation: the "
        f"writer never reached its layout read: {readiness.methods()}"
    )
    assert starttime_of(pid=child) is not None, (
        f"the observed occupant {child} was gone before the adapter's reading, so the "
        "pane it read was not the occupied pane this exercise staged"
    )
    assert outcome.ok is False, "a pane whose foreground is a live child is not launchable"
    assert outcome.pane_id == identity.pane_id, "the created pane must still be named"
    assert outcome.effect_unknown is False, outcome.error
    assert (
        readiness.deliveries() == []
    ), f"the writer delivered into a pane it could not prove: {readiness.deliveries()}"
    assert DAEMON_COMMAND not in pane_capture(
        socket_path=live.socket_path, pane_id=outcome.pane_id
    ), "the command text reached the occupied pane"


def test_the_refusal_preserves_the_partial_layout_and_the_occupying_child(*, live: LiveTab):
    """Refusing the launch must not undo the split, the swap, or kill the occupant.

    The pane is real and correctly placed; the honest outcome is to leave it
    exactly where it is and say so, because that is the state an operator has to
    re-observe. Repeating the swap would push it back below the target.

    The swap is only reached at all because the pane's INITIAL readiness was
    established, so "the proven swap must not be undone" is a claim about a swap
    that really happened rather than about one the sequence stopped short of.
    """
    outcome, readiness = _split_top(live=live)

    _ = _established(readiness=readiness, pane_id=outcome.pane_id)
    child = _observed_occupant(readiness=readiness)
    assert outcome.ok is False, "precondition: the launch was refused"
    tops = _geometry(socket_path=live.socket_path, pane_id=live.original)
    assert outcome.pane_id in tops, "the created pane must survive the refusal"
    assert (
        tops[outcome.pane_id] < tops[live.original]
    ), "the proven swap must not be undone or repeated"
    reading = _reading(socket_path=live.socket_path, pane_id=outcome.pane_id)
    assert reading.is_idle() is False, "the occupying child must not be terminated"
    # The SAME pid that was observed, not merely some process wearing the same
    # name: a replacement child would satisfy a name-only assertion.
    assert child in reading.pids_named(name=OCCUPYING_NAME), reading
    assert starttime_of(pid=child) is not None, f"the occupant {child} was killed"
    assert readiness.methods().count("pane.swap") == 1, readiness.methods()


def test_the_original_pane_and_its_unrelated_sibling_receive_nothing(*, live: LiveTab):
    """The supervised agent and the bystander must both come through untouched.

    The readiness establishment and the late occupation are both confined to the
    pane the ADAPTER created, so these two panes are the same bystanders they
    always were — which the idle readings, the unchanged original shell and the
    distinct shell pids below are what prove.
    """
    before = _geometry(socket_path=live.socket_path, pane_id=live.original)
    original_shell = _reading(socket_path=live.socket_path, pane_id=live.original).shell_pid

    outcome, readiness = _split_top(live=live)

    identity = _established(readiness=readiness, pane_id=outcome.pane_id)
    _ = _observed_occupant(readiness=readiness)
    assert outcome.ok is False, "precondition: the launch was refused"
    for pane_id in (live.original, live.unrelated):
        reading = _reading(socket_path=live.socket_path, pane_id=pane_id)
        assert reading.is_idle(), f"{pane_id} was given something to run: {reading}"
        assert reading.shell_pid != identity.shell_pid, (
            f"{pane_id} reports the created pane's own established shell {identity.shell_pid}, "
            "so this reading is not about a separate pane"
        )
        assert DAEMON_COMMAND not in pane_capture(
            socket_path=live.socket_path, pane_id=pane_id
        ), f"the command text reached {pane_id}"
    after = _geometry(socket_path=live.socket_path, pane_id=live.original)
    assert after[live.unrelated] == before[live.unrelated], "the sibling moved"
    assert (
        _reading(socket_path=live.socket_path, pane_id=live.original).shell_pid == original_shell
    ), "the original pane's shell was replaced"


def test_a_real_transient_is_not_mistaken_for_the_requested_occupant(
    *, live: LiveTab, tmp_path: Path
):
    """The NATIVE control for the measured fixture defect, over real herdr.

    A real, distinctly named, self-terminating child is run in a real pane and
    OBSERVED owning its foreground — the condition the old wait accepted as
    proof of occupation. From that one reading, asking for the REQUESTED name
    must refuse; the requested `sleep` is then started for real and the same
    helper must establish it. Both halves come from the same instrument, so the
    control cannot pass by refusing everything.

    Driven on a pane this control creates itself rather than on the one the
    adapter makes: the subject here is the OBSERVATION, and entangling it with
    a layout sequence would make a refusal ambiguous between the two.
    """
    transient = startup_transient(scratch=tmp_path)
    pane_id = split_pane(
        socket_path=live.socket_path, pane_id=live.unrelated, direction="down", cwd=PANE_CWD
    )

    run_in_pane(socket_path=live.socket_path, pane_id=pane_id, command=transient)
    running = _await_named(socket_path=live.socket_path, pane_id=pane_id, name=TRANSIENT_NAME)
    assert running.is_idle() is False, "the transient really left the shell's foreground group"
    refused = occupying_child_pid(reading=running, name=OCCUPYING_NAME)
    assert refused.pid is None, "a real startup transient was accepted as the requested child"
    assert OCCUPYING_NAME in refused.reason, refused.reason

    run_in_pane(socket_path=live.socket_path, pane_id=pane_id, command=OCCUPYING_COMMAND)
    observed = await_occupying_child(
        read=lambda: process_info_reply(socket_path=live.socket_path, pane_id=pane_id),
        name=OCCUPYING_NAME,
        poll=BoundedPoll(seconds=OCCUPY_TIMEOUT + TRANSIENT_SECONDS),
    )
    assert observed.pid is not None, observed.reason
    assert parent_pid_of(pid=observed.pid) == running.shell_pid, (
        f"the observed {OCCUPYING_NAME} {observed.pid} is not a child of the pane's "
        f"retained shell {running.shell_pid}"
    )


def test_the_staged_transient_is_a_bounded_child_the_shell_recovers_from(
    *, live: LiveTab, tmp_path: Path
):
    """The transient's WHOLE lifecycle, over real herdr: run, bounded, gone, recovered.

    The control above proves the staged transient is not mistaken for the
    requested child. This one proves it is a real child at all — the property the
    measured uutils-host failure destroyed, where the command exited 1 in 0.2
    seconds and no `ovstartup` ever existed, so every exercise that staged one
    refused its own fixture premise.

    Four real observations on one pane this control creates itself, each from the
    server or from `/proc` rather than from the surface under test:

      1. the pane's retained shell as an IDENTITY — pid AND start time — before
         anything runs in it;
      2. the transient observed by its REQUESTED name, as that shell's own
         `/proc` child, owning the pane's foreground group;
      3. its NATURAL exit: this control sends no signal, and the pid no longer
         carries the start time it was observed with, so the process that left
         is the one that arrived rather than a recycled number;
      4. SEPARATELY, within its own bound, the SAME shell identity owning its
         foreground again, with the pane still open.

    Step 4 is `await_idle_shell` doing the job a predecessor inferred from step 3
    — the child exiting is not the shell recovering — and step 1's pin is what
    makes "the same shell" a claim about a process rather than about an integer.
    """
    pane_id = split_pane(
        socket_path=live.socket_path, pane_id=live.unrelated, direction="down", cwd=PANE_CWD
    )

    def read() -> dict[str, Any]:
        return process_info_reply(socket_path=live.socket_path, pane_id=pane_id)

    shell = _reading(socket_path=live.socket_path, pane_id=pane_id).shell_pid
    shell_starttime = starttime_of(pid=shell)
    assert shell_starttime is not None, f"the pane's shell {shell} must be alive to begin with"

    run_in_pane(
        socket_path=live.socket_path, pane_id=pane_id, command=startup_transient(scratch=tmp_path)
    )
    observed = await_occupying_child(
        read=read, name=TRANSIENT_NAME, poll=BoundedPoll(seconds=OCCUPY_TIMEOUT)
    )
    assert observed.pid is not None, observed.reason
    child_starttime = starttime_of(pid=observed.pid)
    assert child_starttime is not None, f"{TRANSIENT_NAME} {observed.pid} was gone when observed"

    recovery = await_idle_shell(
        read=read,
        pane_id=pane_id,
        poll=BoundedPoll(seconds=OCCUPY_TIMEOUT + TRANSIENT_SECONDS),
        expected=ShellIdentityPin(pid=shell, starttime=shell_starttime),
    )

    assert recovery.recovered is True, recovery.reason
    assert starttime_of(pid=observed.pid) != child_starttime, (
        f"{TRANSIENT_NAME} {observed.pid} still carries start time {child_starttime}, so the "
        "pane reported an idle shell while its declared transient was still running"
    )


# ------------------------------- the bounded named-child observation itself


# The pane and the pids are the operator host's, carried over from the shared
# module's own scripted controls so the two describe ONE measured situation.
OBSERVED_PANE = "w1:p4"
OBSERVED_SHELL_PID = 3584980
OBSERVED_TRANSIENT_PID = 3585294
OBSERVED_FOREIGN_PID = 3585295
# The real foreground process measured on the operator host: a child of `zsh`'s
# own startup, usable and coherent, and simply not what anyone asked for.
FOREIGN_NAME = "mv"
# An envelope carrying no `process_info` at all. `read_foreground` reduces it to
# None — an UNSUCCESSFUL OBSERVATION, which is a fact about the READING rather
# than about the pane, and is the condition a bounded wait has to look past.
UNUSABLE_REPLY: dict[str, Any] = {"result": {}}
# Deliberately not a socket: every reading in this section comes from the
# scripted seam, so a path that could never connect proves none of them went out.
SCRIPTED_SOCKET = "/nonexistent/scripted-observations.sock"


@dataclass(frozen=True, kw_only=True)
class _Clock:
    """The two `time` entries a bounded wait reads, under a control's command.

    Field-held callables rather than methods, mirroring the shared `BoundedPoll`,
    so a wait's own `time.monotonic()` and `time.sleep(...)` calls reach them
    unchanged.
    """

    monotonic: Callable[[], float]
    sleep: Callable[[float], None]


def _named_reply(*, pid: int, name: str) -> dict[str, Any]:
    """A `pane.process_info` reply whose foreground is `pid`, listed as `name`."""
    return {
        "result": {
            "process_info": {
                "pane_id": OBSERVED_PANE,
                "shell_pid": OBSERVED_SHELL_PID,
                "foreground_process_group_id": pid,
                "foreground_processes": [
                    {"pid": pid, "name": name, "cmdline": name, "cwd": PANE_CWD}
                ],
            }
        }
    }


def _scripted_observations(
    *, monkeypatch: pytest.MonkeyPatch, replies: list[dict[str, Any]]
) -> list[str]:
    """Interpose THIS module's OWN observation seam with `replies`, in order.

    The seam is `process_info_reply`, which is how every pane in this module is
    already read, so a control drives the wait from exactly where the real server
    does: no parameter is added, and the helper under test is entered unchanged.

    The LAST reply repeats indefinitely, which is what lets a control describe a
    PERMANENT condition without sizing a list against the wait's poll count.

    Returns the pane ids actually asked for, in order. That list is how a control
    tells "looked again" apart from "answered on the first reading".
    """
    remaining = list(replies)
    asked: list[str] = []

    def observe(*, socket_path: str, pane_id: str) -> dict[str, Any]:
        _ = socket_path
        asked.append(pane_id)
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    monkeypatch.setattr(f"{__name__}.process_info_reply", observe)
    return asked


def _frozen_clock(*, monkeypatch: pytest.MonkeyPatch, ticks: list[float]) -> None:
    """Advance THIS module's clock only through `ticks`, and never really sleep.

    A DISCLOSED fault control over the wait's CLOCK, never over its observations.
    It makes no claim about the historical host timing, and it is here only so a
    deadline control does not spend `OCCUPY_TIMEOUT` real seconds asserting a
    timer. The bound itself is untouched, and nothing it does is visible to the
    native exercises above, which read the real clock.

    Three ticks minimum, for the reason the shared `_frozen_poll` records: the
    wait reads the clock once to compute its deadline and again on each `while`
    test, so an intermediate tick is what buys exactly one reading before expiry.
    """
    remaining = list(ticks)

    def monotonic() -> float:
        return remaining.pop(0) if remaining else 1e9

    monkeypatch.setattr(
        f"{__name__}.time", _Clock(monotonic=monotonic, sleep=lambda _seconds: None)
    )


def test_a_one_shot_unusable_reading_does_not_end_the_named_child_wait(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE separately observed host failure: one unusable reply ended the exercise.

    `_await_named` promises the FIRST reading in which the pane lists a
    foreground process by name, within its own bound. It took those readings
    through `_reading`, whose `assert` is right for a SINGLE-SHOT caller and
    wrong inside a poll: one unavailable reply is a fact about the READING, not
    about the pane, and it failed the whole exercise — in the measured host run,
    before the layout adapter had been entered at all.

    One unusable reply, then the real expected observation. The bound is not
    touched and this control waits for nothing in real time beyond the wait's own
    existing poll interval; the second reading is simply TAKEN, which is the
    behaviour the promise already claimed.

    This is post-command child observation, not initial readiness and not a
    production guard, and the controlled unavailability makes no claim to
    reproduce the historical timing — only to put the question.
    """
    asked = _scripted_observations(
        monkeypatch=monkeypatch,
        replies=[
            UNUSABLE_REPLY,
            _named_reply(pid=OBSERVED_TRANSIENT_PID, name=TRANSIENT_NAME),
        ],
    )

    reading = _await_named(socket_path=SCRIPTED_SOCKET, pane_id=OBSERVED_PANE, name=TRANSIENT_NAME)

    assert asked == [OBSERVED_PANE, OBSERVED_PANE], (
        f"the wait took {len(asked)} reading(s), {asked}; an unusable FIRST reading must be "
        "followed by a second of the same pane rather than ending the exercise"
    )
    # The EXPECTED child's identity, not merely a reading that came back: the
    # returned observation has to be the one that actually lists it.
    assert reading.pane_id == OBSERVED_PANE, reading
    assert reading.shell_pid == OBSERVED_SHELL_PID, reading
    assert reading.pids_named(name=TRANSIENT_NAME) == (OBSERVED_TRANSIENT_PID,), reading


def test_a_permanently_unavailable_reading_is_a_bounded_named_wait_failure(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tolerating one gap must not become waiting forever, nor failing for the wrong thing.

    Every reading is unusable. The wait must still END at its own bound and fail
    NAMING what it was waiting for AND why no reading could answer, so an
    operator learns that the pane never reported the process rather than that one
    control read came back empty. Failing on the first unusable reply — what the
    measured helper did — reports a failed control read as though it were an
    answer about the pane.
    """
    _frozen_clock(monkeypatch=monkeypatch, ticks=[0.0, 1.0, OCCUPY_TIMEOUT + 1.0])
    asked = _scripted_observations(monkeypatch=monkeypatch, replies=[UNUSABLE_REPLY])

    with pytest.raises(pytest.fail.Exception) as refusal:
        _await_named(socket_path=SCRIPTED_SOCKET, pane_id=OBSERVED_PANE, name=TRANSIENT_NAME)

    assert asked == [OBSERVED_PANE], f"the bound must hold the readings to exactly one: {asked}"
    assert OBSERVED_PANE in str(refusal.value), refusal.value
    assert TRANSIENT_NAME in str(refusal.value), refusal.value
    assert "usable" in str(
        refusal.value
    ), f"the bounded failure does not say why no reading could answer: {refusal.value}"


def test_a_foreign_foreground_process_is_never_returned_as_the_named_child(
    *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A usable reading about ANOTHER process is refused, and the refusal says which.

    Two halves, disclosed separately because they stood differently before the
    repair. The REJECTION held already: a reading that lists no process under the
    requested name was never returned, and tolerating an unusable reading must
    not slacken into tolerating a usable one that is simply about something else.
    The REPORT did not hold: the expiry named only what was awaited, so the
    operator could not see that the pane's foreground was held by the real `mv`
    from shell startup measured on the host — the very process whose silent
    acceptance this family's original defect turned on.
    """
    _frozen_clock(monkeypatch=monkeypatch, ticks=[0.0, 1.0, OCCUPY_TIMEOUT + 1.0])
    asked = _scripted_observations(
        monkeypatch=monkeypatch,
        replies=[_named_reply(pid=OBSERVED_FOREIGN_PID, name=FOREIGN_NAME)],
    )

    with pytest.raises(pytest.fail.Exception) as refusal:
        _await_named(socket_path=SCRIPTED_SOCKET, pane_id=OBSERVED_PANE, name=TRANSIENT_NAME)

    assert asked == [OBSERVED_PANE], f"the bound must hold the readings to exactly one: {asked}"
    assert TRANSIENT_NAME in str(refusal.value), refusal.value
    assert FOREIGN_NAME in str(refusal.value), (
        "the bounded failure does not report what the pane's foreground actually held: "
        f"{refusal.value}"
    )
