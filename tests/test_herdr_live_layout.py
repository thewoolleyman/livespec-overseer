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
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from test_herdr_live_observations import (
    BoundedPoll,
    ForegroundReading,
    PaneIdentity,
    PaneReadiness,
    ReadyWriter,
    await_occupying_child,
    parent_pid_of,
    process_info_reply,
    read_foreground,
    registered_login_shells,
    split_pane,
    start_owned_server,
    startup_transient,
    stop_owned_server,
)

__all__: list[str] = []

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "overseer"
WRITE_CALLS_PATH = PACKAGE_DIR / "herdr_write_calls.py"
WRITER_PATH = PACKAGE_DIR / "herdr_write.py"

HERDR_BINARY = "herdr"
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
    """Spawn a detached OWNED herdr server and build a tab holding TWO existing panes.

    **The server is started through the shared `start_owned_server` seam, which is
    the repair.** This used to spawn `herdr server` with the AMBIENT environment and
    no configuration of its own, so which shell its panes came up in — and which
    startup files that shell ran — were the operator's choices rather than this
    fixture's. The shared seam declares both: a fixture-owned private config selects
    an available, REGISTERED minimal shell in `non_login` mode, and the one
    interactive startup hook `non_login` does not close is excluded from the
    launched server's copied child environment. Everything else about the parent
    environment is preserved verbatim, and the parent's own environment is never
    mutated.

    `test_the_fixture_server_runs_a_declared_minimal_shell_despite_an_inherited_config`
    is the regression over exactly that, driven through this function.
    """
    owned = start_owned_server(session=session, scratch=scratch, cwd=PANE_CWD)
    # A sibling the operation has no business touching. Split to the RIGHT so it
    # occupies its own column and any vertical reshuffle of the original's column
    # would show up as a change to this pane's own rectangle.
    #
    # Enclosed in cleanup: the server is this fixture's own resource from the moment
    # the seam returned it, and a failed sibling split used to leave it running.
    try:
        unrelated = split_pane(
            socket_path=owned.socket_path,
            pane_id=owned.root,
            direction="right",
            cwd=PANE_CWD,
        )
    except BaseException:
        _stop_live_herdr(session=session)
        raise
    return LiveTab(
        socket_path=owned.socket_path,
        server_pid=owned.server_pid,
        original=owned.root,
        unrelated=unrelated,
        transient=startup_transient(scratch=scratch),
    )


def _stop_live_herdr(*, session: str) -> None:
    """Stop and delete ONLY this session, by its exact name."""
    stop_owned_server(session=session)


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


def _split_top(*, live: LiveTab) -> tuple[Any, PaneReadiness]:
    """The writer's own PUBLIC entrypoint, with the created pane's readiness ESTABLISHED.

    **This enters `HerdrWriter.split_window_top` rather than
    `herdr_layout.place_above`, and that is the repair.** The public facade is what
    the two-pane bootstrap actually calls, so it is what this exercise drives; a
    sequence entered one layer below it is a different subject, and the
    inherited-facade assertion below is what keeps a fixture from quietly reducing
    the coverage to the internal layout call again.

    The seam is `ReadyWriter` — the shipped writer with its PUBLIC `request`
    interposed — so the socket, the per-request deadline, the peer revalidation
    against the REAL server whose pid and `/proc` start time this target names, and
    the `ShellProof` built from the writer's own fields are all the shipped facade's.
    Its only effect is to establish the EXACT created pane's available and coherent
    identity between two of the writer's own requests, where it costs no request its
    deadline.
    """
    _calls, writer_module = _modules()
    identity = importlib.import_module("herdr_identity")
    assert (
        ReadyWriter.split_window_top is writer_module.HerdrWriter.split_window_top
    ), "the exercise must enter the SHIPPED public facade, not a fixture reimplementation"
    readiness = PaneReadiness(
        socket_path=live.socket_path,
        transient=live.transient,
        registered=registered_login_shells(),
    )
    outcome = ReadyWriter(readiness=readiness).split_window_top(
        target=_target(identity=identity, live=live),
        cwd=PANE_CWD,
        command=LAUNCH_COMMAND,
        ratio=TOP_RATIO,
    )
    return outcome, readiness


def _established(*, readiness: PaneReadiness, pane_id: str) -> PaneIdentity:
    """Grade the created pane's readiness premise before anything grades the adapter.

    Each fact separately, so a failure says which one was missing: the step ran
    exactly once and for the pane the writer created, the gate established what it
    establishes, the staged child was the pinned shell's own and exited, that shell
    recovered, and the pane's two shell descriptions agree about it. An unavailable
    or contradictory observation therefore fails HERE, carrying the bound it expired
    under, rather than being reported as the adapter declining a launch.
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
    pane_identity = readiness.identity
    assert pane_identity is not None and pane_identity.coherent is True, readiness.refusal()
    assert pane_identity.shell_pid == gate.retained.pid, (
        f"the coherent identity describes shell {pane_identity.shell_pid} while the pinned "
        f"retained shell is {gate.retained.pid}"
    )
    return pane_identity


def test_the_new_pane_is_placed_above_the_original(*, live: LiveTab):
    """A new pane appears, and it sits strictly ABOVE the pane that was targeted.

    Herdr cannot split upward, so getting this wrong is the natural failure: a
    plain `down` split would leave the daemon BELOW the agent it supervises.
    """
    before, _focused = _geometry(live=live)

    outcome, readiness = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    established = _established(readiness=readiness, pane_id=outcome.pane_id)
    after, _ = _geometry(live=live)
    assert outcome.pane_id not in before, "split_window_top must create a NEW pane"
    assert outcome.pane_id in after, after
    new_top, _new_height = after[outcome.pane_id]
    original_top, _original_height = after[live.original]
    assert new_top < original_top, f"new pane at {new_top} is not above {original_top}"
    assert established.pane_id == outcome.pane_id, (
        "the pane placed above must be the pane whose readiness was established: "
        f"{established.pane_id!r} against {outcome.pane_id!r}"
    )


def test_the_requested_command_runs_in_the_new_pane_s_retained_shell(*, live: LiveTab):
    """The command is the new pane's FOREGROUND process, and its shell survives.

    A retained shell is what makes the pane reusable and keeps it from closing
    when the command exits, so `shell_pid` must be present AND distinct from the
    command's own process group — and the child must be that shell's own, read
    from `/proc`, on the EXACT pane the operation says it created.
    """
    outcome, readiness = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    established = _established(readiness=readiness, pane_id=outcome.pane_id)
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
    # The SAME retained shell readiness was established on, not merely whichever shell
    # the pane reported afterwards: a replacement would satisfy every assertion above.
    assert reading.shell_pid == established.shell_pid, (
        f"the command runs under shell {reading.shell_pid}, not the established retained "
        f"shell {established.shell_pid}"
    )
    assert readiness.deliveries() == [
        (outcome.pane_id, LAUNCH_COMMAND, ("Enter",))
    ], readiness.deliveries()


def test_the_original_pane_keeps_its_identity_and_its_focus(*, live: LiveTab):
    """The supervised session must survive the split completely untouched."""
    before_reading = _reading(live=live, pane_id=live.original)
    _before, focused_before = _geometry(live=live)
    assert focused_before == live.original, "fixture precondition: the original is focused"

    outcome, readiness = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    established = _established(readiness=readiness, pane_id=outcome.pane_id)
    after, focused_after = _geometry(live=live)
    after_reading = _reading(live=live, pane_id=live.original)
    assert live.original in after, "the original pane id must survive"
    assert (
        after_reading.shell_pid == before_reading.shell_pid
    ), "the original pane's shell must not be replaced"
    assert after_reading.is_idle(), f"the original pane was given something to run: {after_reading}"
    assert after_reading.shell_pid != established.shell_pid, (
        "the original pane must be a DIFFERENT shell process from the created pane, so the "
        f"reading above is about the supervised session; both report {established.shell_pid}"
    )
    assert focused_after == live.original, f"focus moved to {focused_after}"


def test_an_unrelated_pane_is_left_exactly_where_it_was(*, live: LiveTab):
    """Everything else on the tab keeps its geometry and its process identity."""
    before, _focused = _geometry(live=live)
    before_reading = _reading(live=live, pane_id=live.unrelated)

    outcome, readiness = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    established = _established(readiness=readiness, pane_id=outcome.pane_id)
    after, _ = _geometry(live=live)
    after_reading = _reading(live=live, pane_id=live.unrelated)
    assert (
        after[live.unrelated] == before[live.unrelated]
    ), f"unrelated pane moved from {before[live.unrelated]} to {after[live.unrelated]}"
    assert after_reading.shell_pid == before_reading.shell_pid
    assert after_reading.is_idle(), f"the sibling was given something to run: {after_reading}"
    assert after_reading.shell_pid != established.shell_pid, (
        "the sibling must be a DIFFERENT shell process from the created pane; both report "
        f"{established.shell_pid}"
    )


def test_the_new_top_pane_takes_the_requested_percentage(*, live: LiveTab):
    """Geometry is a PERCENTAGE of the original pane's column, not a row count.

    `ratio` is the original's share of the split, so after the swap the new top
    pane holds that share — which is what lets a caller ask for "a quarter" and
    get it at any terminal size.
    """
    outcome, readiness = _split_top(live=live)

    assert outcome.ok is True, outcome.error
    _ = _established(readiness=readiness, pane_id=outcome.pane_id)
    after, _ = _geometry(live=live)
    _new_top, new_height = after[outcome.pane_id]
    _original_top, original_height = after[live.original]
    column = new_height + original_height
    assert (
        abs(new_height - round(column * TOP_RATIO)) <= 1
    ), f"new pane height {new_height} is not {TOP_RATIO} of the {column}-row column"


# ------------------- the fixture's OWN shell and startup files, as a premise
#
# The accepted behavioural regression for work-item `overseer-3zfpz5`. It drives
# the DELIVERED server-start entrypoint `_start_live_tab` and fails on what that
# entrypoint does with an inherited configuration, not on a symbol it lacks.
#
# Every staging helper below is local to this exercise on purpose: the subject is
# the entrypoint's behaviour, and a premise borrowed from the seam under repair
# would only prove that seam self-consistent.

# Printed by the staged `$ENV` startup file, which also creates a file of this
# name. Two independent witnesses, because a capture is a RENDERING while a file
# is a side effect.
STARTUP_MARKER = "OVSTARTUPRAN1"
# The MINIMAL shell family a controlled fixture should be able to declare. Minimal
# is the point: the fewer startup hooks a pane's shell has, the less of an exercise
# depends on host configuration.
MINIMAL_SHELL_NAME = "dash"
MINIMAL_SHELL_CANDIDATES = ("/usr/bin/dash", "/bin/dash")
# The RIVAL the inherited configuration names — a different shell this host also
# registers, so the conflict is one herdr would genuinely have honoured.
RIVAL_SHELL_CANDIDATES = ("/bin/bash", "/usr/bin/bash")
LOGIN_SHELL_REGISTRY = "/etc/shells"


def _registered_resolved_shells() -> set[str]:
    """Every login shell this host's own register declares, resolved."""
    try:
        raw = Path(LOGIN_SHELL_REGISTRY).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return {
        os.path.realpath(entry)
        for entry in (line.strip() for line in raw.splitlines())
        if entry and not entry.startswith("#")
    }


def _first_registered(*, candidates: tuple[str, ...], registered: set[str]) -> str | None:
    """The first candidate this host both REGISTERS and can execute, or None."""
    for candidate in candidates:
        resolved = os.path.realpath(candidate)
        if resolved in registered and os.access(resolved, os.X_OK):
            return candidate
    return None


def _write_rival_config(*, scratch: Path, rival: str) -> Path:
    """A REAL herdr config selecting `rival` in `login` mode, for inheritance.

    Not a stub: herdr parses this file and would obey it. `herdr --default-config`
    documents `[terminal] default_shell` and `shell_mode`, and `HERDR_CONFIG_PATH`
    is what selects which config file a herdr process reads.
    """
    directory = scratch / "rival-config"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "herdr-config.toml"
    _ = path.write_text(
        f'[terminal]\ndefault_shell = "{rival}"\nshell_mode = "login"\n', encoding="utf-8"
    )
    return path


def _stage_conflicting_inherited_setup(
    *, scratch: Path, monkeypatch: pytest.MonkeyPatch, rival: str
) -> Path:
    """A rival config and an interactive startup file, reaching the server by INHERITANCE.

    Returns the path the startup file creates when it runs, which is one of the
    two witnesses that it did not.
    """
    ran = scratch / f"{STARTUP_MARKER}.ran"
    startup = scratch / "interactive-startup.sh"
    _ = startup.write_text(f"printf '%s\\n' {STARTUP_MARKER}\n: > {ran}\n", encoding="utf-8")
    monkeypatch.setenv("HERDR_CONFIG_PATH", str(_write_rival_config(scratch=scratch, rival=rival)))
    monkeypatch.setenv("ENV", str(startup))
    return ran


def _umask_of(*, pid: int) -> str:
    """`pid`'s umask as the KERNEL reports it, or ``""`` when `/proc` omits it."""
    for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("Umask:"):
            return line.split(":", 1)[1].strip()
    return ""


def _environ_of(*, pid: int) -> dict[str, str]:
    """`pid`'s own environment, read from `/proc` — what the child ACTUALLY got."""
    raw = Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", errors="replace")
    return dict(entry.split("=", 1) for entry in raw.split("\0") if "=" in entry)


def _kernel_executable_of(*, pid: int) -> str | None:
    """`pid`'s resolved `/proc/<pid>/exe`, or None when that half is unavailable.

    `readlink` rather than a realpath of the magic link: resolving the PATH of a
    process that is GONE answers `/proc/<pid>/exe` unchanged, which would
    manufacture an executable for a dead pid.
    """
    try:
        return str(Path(f"/proc/{pid}/exe").readlink().resolve())
    except OSError:
        return None


@dataclass(frozen=True, kw_only=True)
class _OwnedSetup:
    """Everything read off one live tab WHILE its server was still running.

    Gathered in one pass and asserted afterwards, because each field is a reading
    about a LIVE process: `/proc/<shell_pid>/exe` answers None once the pane's
    shell is gone, and teardown ends it.
    """

    reading: ForegroundReading
    leader_names: tuple[str, ...]
    executable: str | None
    capture: str
    child: dict[str, str]
    umask: str


def _observe_setup(*, live: LiveTab) -> _OwnedSetup:
    """One pass of real readings about `live`'s original pane and its server child."""
    reading = _reading(live=live, pane_id=live.original)
    reply = _raw_request(
        socket_path=live.socket_path,
        method="pane.read",
        params={
            "pane_id": live.original,
            "source": "visible",
            "format": "text",
            "strip_ansi": True,
        },
    )
    return _OwnedSetup(
        reading=reading,
        leader_names=tuple(name for pid, name in reading.processes if pid == reading.group_id),
        executable=_kernel_executable_of(pid=reading.shell_pid),
        capture=str(reply["result"]["read"]["text"]),
        child=_environ_of(pid=live.server_pid),
        umask=_umask_of(pid=live.server_pid),
    )


def _assert_parent_setup_preserved(
    *, observed: _OwnedSetup, inherited: dict[str, str], own_umask: str
) -> None:
    """The launched server's environment differs from the parent's in exactly two ways.

    Its herdr configuration is NOT the inherited one, and the interactive startup
    variable is gone. Everything named here reaches the child verbatim, the umask is
    the inherited one, and this process's own environment still carries the hostile
    values — a seam that mutated `os.environ` would leak into every later exercise.
    """
    child = observed.child
    assert (
        child.get("HERDR_CONFIG_PATH") != inherited["HERDR_CONFIG_PATH"]
    ), f"the server inherited the rival configuration: {child.get('HERDR_CONFIG_PATH')!r}"
    assert "ENV" not in child, "the interactive startup variable reached the child"
    for name in ("HOME", "PATH", "SHELL", "CODEX_HOME"):
        assert child.get(name) == inherited.get(
            name
        ), f"{name} was not preserved: {child.get(name)}"
    assert (
        observed.umask == own_umask
    ), f"the child's umask is {observed.umask!r}, not the inherited {own_umask!r}"
    assert os.environ["HERDR_CONFIG_PATH"] == inherited["HERDR_CONFIG_PATH"], "parent was mutated"
    assert os.environ["ENV"] == inherited["ENV"], "the parent's own $ENV was mutated"


def test_the_fixture_server_runs_a_declared_minimal_shell_despite_an_inherited_config(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """THE setup premise: the fixture's own shell choice wins, and no startup file runs.

    This exercise drives the delivered server-start entrypoint `_start_live_tab`
    under an ambient environment staged to contradict it, and asserts three things
    about the real server that came back:

      1. **The panes run a declared MINIMAL shell, coherently.** The inherited
         `HERDR_CONFIG_PATH` names a real config selecting a DIFFERENT registered
         shell in `login` mode. The pane's server-reported leader name and the
         kernel's `/proc/<pid>/exe` must both describe one `dash` executable this
         host REGISTERS — and not the rival.
      2. **No interactive startup file ran.** `$ENV` names a real script that
         prints a marker and creates a file; both witnesses must come up empty.
      3. **The parent setup is otherwise preserved, and never mutated.**

    Which shell a pane comes up in is the premise every other native exercise in
    this family rests on, and it was the operator's choice rather than the
    fixture's: a server started with the ambient environment obeys whatever
    `HERDR_CONFIG_PATH` and `$SHELL` it inherits, and runs whatever `$ENV` names.
    """
    if shutil.which(HERDR_BINARY) is None:
        pytest.skip("herdr is not installed on this host")
    registered = _registered_resolved_shells()
    minimal = _first_registered(candidates=MINIMAL_SHELL_CANDIDATES, registered=registered)
    rival = _first_registered(candidates=RIVAL_SHELL_CANDIDATES, registered=registered)
    if minimal is None or rival is None:
        pytest.skip(
            f"{LOGIN_SHELL_REGISTRY} must register both a {MINIMAL_SHELL_NAME} and a rival shell; "
            f"it registers {sorted(registered)}"
        )
    ran = _stage_conflicting_inherited_setup(scratch=tmp_path, monkeypatch=monkeypatch, rival=rival)
    inherited = dict(os.environ)
    own_umask = _umask_of(pid=os.getpid())
    session = f"overseer-test-{os.getpid()}-declared-shell"

    live = _start_live_tab(session=session, scratch=tmp_path)
    try:
        observed = _observe_setup(live=live)
    finally:
        _stop_live_herdr(session=session)

    assert observed.reading.is_idle(), f"the pane must be idle to testify: {observed.reading}"
    assert observed.executable is not None, "the kernel half of the pane's shell is unavailable"
    assert Path(observed.executable).name == MINIMAL_SHELL_NAME, (
        f"the pane's shell is {observed.executable!r}, not a {MINIMAL_SHELL_NAME!r}; the "
        f"inherited configuration selecting {rival!r} was obeyed"
    )
    assert observed.executable in registered, (
        f"{observed.executable!r} is not one of the login shells {LOGIN_SHELL_REGISTRY} "
        f"registers, so it is not a shell the retained-shell proof may mediate"
    )
    assert observed.executable != os.path.realpath(rival), "the rival shell was used"
    assert observed.leader_names == (Path(observed.executable).name,), (
        f"herdr reports {list(observed.leader_names)} for the pane's own shell while the kernel "
        f"runs {observed.executable!r}; the two must describe ONE program"
    )
    assert not ran.exists(), f"the inherited $ENV startup file ran and created {ran}"
    assert (
        STARTUP_MARKER not in observed.capture
    ), f"the startup marker reached the pane: {observed.capture!r}"
    _assert_parent_setup_preserved(observed=observed, inherited=inherited, own_umask=own_umask)
