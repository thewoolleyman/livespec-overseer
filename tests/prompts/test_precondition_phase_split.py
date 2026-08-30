"""The HALT preconditions are split by PHASE, and the drive gate still fires.

`overseer-2a1`: a charter could not be authored for a NEWLY CREATED plan thread,
because four of the five HALT-first preconditions presuppose a session already
working the topic. The skill was never misbehaving — it halted, named the failing
check and the expected session name, and refused to fabricate a session. The
defect was an ORDERING assumption, and the maintainer ratified shape (ii) on
2026-08-23: artifact-only checks gate AUTHORING, live-session checks gate
DRIVING.

MOVING A CHECK IS HOW A CHECK QUIETLY STOPS EXISTING, so a green authoring leg
alone would not mean anything here. The load-bearing legs are the drive-time
controls: the same four checks, run against a tmux server with no sessions in
it, must still HALT with byte-identical messages and byte-identical expected
names — and against a live rigged pair they must still PASS, because a "remedy"
that halts unconditionally would satisfy the negative legs on its own.

SCOPE, STATED RATHER THAN HIDDEN. The exactly-one-place legs read the GENERATOR
CONTRACT — `.claude-plugin/prose/supervise-plan.md` — which is the surface the
ruling changed. Charters already emitted under the pre-split generator are
historical artifacts of their generation and are deliberately not rewritten;
`test_stale_cache_generation_is_detectable.py` owns that axis.

NO SKIPS. tmux absence FAILS rather than skips, for the reason recorded on the
shared rig's own guard in `conftest.py`: a skipped leg proves nothing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from overseer.prompt_tmux import wait_for_pane_current_path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROSE = _REPO_ROOT / ".claude-plugin" / "prose" / "supervise-plan.md"
_SHARED_LAYER = _REPO_ROOT / ".ai" / "supervisor-protocol.md"
_WORKAROUND_RECORD = (
    _REPO_ROOT / "plan" / "archive" / "codex-parity-and-rollout-safety" / "handoff.md"
)

# ALL FIVE, BY NAME, WITH THEIR PHASE — acceptance leg 4. Stated here as data so
# the split is exhaustive rather than approximate: a precondition missing from
# this table, or appearing under two phases in the prose, reddens the partition
# leg below. Precondition 4 is the artifact check and the only authoring gate.
_EXPECTED_PHASE = {
    "worker-session-exists": "drive",
    "worker-pane-holds-live-agent": "drive",
    "supervisor-session-live-and-distinct": "drive",
    "plan-directory-exists": "authoring",
    "worker-pane-cwd-inside-repo": "drive",
}

_TOPIC = "pcs2a1"
_WORKER = _TOPIC
# A strict PREFIX of the supervisor name, deliberately: that is C1's hazard, and
# it keeps the distinct-pane guard in precondition 3 under real load here.
_SUPERVISOR = f"{_TOPIC}-supervisor"

# The exact HALT line and the exact REMEDY line each drive check must still emit
# when its session is absent. Pinned as literals — not derived from the prose —
# so a reworded message is a RED rather than a silently-tracked rename.
_DRIVE_HALT = {
    "worker-session-exists": (
        "HALT: expected worker session 'pcs2a1'",
        "REMEDY: ask the maintainer whether to start that worker session",
    ),
    "worker-pane-holds-live-agent": (
        "HALT: empty pane_pid for 'pcs2a1'",
        "REMEDY: re-check the exact worker target and stop if it still resolves empty",
    ),
    "supervisor-session-live-and-distinct": (
        "HALT: expected supervisor session 'pcs2a1-supervisor'",
        "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it",
    ),
    "worker-pane-cwd-inside-repo": (
        "HALT: empty pane_current_path for 'pcs2a1'",
        "REMEDY: re-check the exact worker target and stop if it still resolves empty",
    ),
}

# What a PASSING run of each drive check must actually print. Without this the
# positive control degenerates into "exit 0", which a block that does nothing
# also satisfies — the blind spot the cold-open gate's own boot-block comment
# records. The empty string is a deliberate no-evidence case: precondition 1 is
# a bare existence probe and prints nothing on success.
_DRIVE_PASS_EVIDENCE = {
    "worker-session-exists": "",
    "worker-pane-holds-live-agent": "claude",
    "supervisor-session-live-and-distinct": "claude",
    "worker-pane-cwd-inside-repo": "PASS: ",
}

# Verbs that would MANUFACTURE the state a gate asks about. None may appear in
# any precondition block, in either phase.
_FABRICATING_VERBS = (
    "new-session",
    "new-window",
    "split-window",
    "respawn-pane",
    "kill-session",
    "kill-server",
)

_NO_FABRICATION_RULE = (
    "Do not create a\nmissing session, do not fall back to another session, and do not proceed\n"
    "read-only."
)
_RETIRED_PRESCRIPTION = "how to repeat it on the next thread"
_RETIREMENT_NOTE = "RETIRED by `overseer-2a1`"

_ITEM = re.compile(r"(?m)^(?P<num>\d+)\. `(?P<name>[a-z-]+)`")
_FENCE = re.compile(r"(?ms)^```(?:bash|sh)\n(?P<body>.*?)^```")
_TABLE_ROW = re.compile(r"(?m)^\|\s*\d+\s*\|\s*`(?P<name>[a-z-]+)`\s*\|\s*(?P<phase>\w+)\s*\|")


def _section() -> str:
    """The generator's own `## HALT-first preconditions` section, and only it."""
    text = _PROSE.read_text(encoding="utf-8")
    return text[text.find("## HALT-first preconditions") :].split("\n## ", 1)[0]


def _phase_bodies() -> dict[str, str]:
    """Each `### <phase> phase` subsection, keyed by the phase's first word."""
    parts = re.split(r"(?m)^### ", _section())[1:]
    return {part.split(maxsplit=1)[0].lower(): part for part in parts}


def _units() -> list[tuple[str, str, str]]:
    """(phase, precondition-name, its prose) for every numbered precondition."""
    units: list[tuple[str, str, str]] = []
    for phase, body in _phase_bodies().items():
        marks = list(_ITEM.finditer(body))
        for index, mark in enumerate(marks):
            end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
            units.append((phase, mark.group("name"), body[mark.start() : end]))
    return units


def _blocks(*, body: str) -> list[str]:
    return [match.group("body") for match in _FENCE.finditer(body)]


def _runnable(*, body: str, repo: Path) -> str:
    """The block with every generation-time placeholder bound to the rig."""
    return (
        "\n".join(_blocks(body=body))
        .replace("<worker-session>", _WORKER)
        .replace("<supervisor-session>", _SUPERVISOR)
        .replace("<absolute-target-repo>", str(repo))
        .replace("<topic>", _TOPIC)
    )


def _scripts_by_name(*, repo: Path) -> dict[str, str]:
    return {name: _runnable(body=body, repo=repo) for _, name, body in _units()}


def _tmux_on(socket: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Address a PRIVATE socket. The maintainer's default socket is never used.

    S603/S607 suppressed on the same narrow reasoning as the sibling modules: the
    argv is a LIST with no shell and no untrusted input, and resolving `tmux`
    through PATH is load-bearing so the leg exercises the environment's own tmux.
    """
    return subprocess.run(  # noqa: S603
        ["tmux", "-L", socket, *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _run(*, script: str, path: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Execute one emitted block under an explicit PATH.

    `bash` is resolved ABSOLUTELY because the authoring leg hands the child a
    PATH with nothing on it — the whole point of that leg — and executable
    lookup would otherwise fail for the rig's reason rather than the contract's.
    """
    env = dict(os.environ)
    env["PATH"] = path
    return subprocess.run(  # noqa: S603
        [_bash(), "-c", script],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=30,
        check=False,
    )


def _require(*, tool: str) -> str:
    resolved = shutil.which(tool)
    # COVERAGE-EXEMPT ON PURPOSE, and do NOT delete it as dead code: it is
    # unreachable exactly when the tool IS present, i.e. on every run that
    # reaches 100% coverage. Removing it restores skip-on-missing-tool, which is
    # the defect class the shared rig's guard exists to refuse.
    if resolved is None:  # pragma: no cover
        pytest.fail(f"{tool} is required by this contract's acceptance and is absent")
    return resolved


def _bash() -> str:
    return _require(tool="bash")


@pytest.fixture(name="socket")
def _socket_fixture(*, tmp_path: Path) -> Iterator[str]:
    """A private tmux socket, unique per test AND per run, killed in a finally."""
    name = f"phase-{os.getpid()}-{tmp_path.name}"
    try:
        yield name
    finally:
        _tmux_on(name, "kill-server")
        base = Path(os.environ.get("TMUX_TMPDIR", "/tmp"))
        (base / f"tmux-{os.getuid()}" / name).unlink(missing_ok=True)


@pytest.fixture(name="tmux_path")
def _tmux_path_fixture(*, tmp_path: Path, socket: str) -> str:
    """A PATH whose `tmux` is a shim bound to this test's private socket.

    The emitted blocks call a bare `tmux`, exactly as a supervisor would. Binding
    the socket in a shim is what lets them run unmodified without ever addressing
    the maintainer's default server.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "tmux"
    shim.write_text(f'#!/bin/sh\nexec {_require(tool="tmux")} -L {socket} "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


@pytest.fixture(name="repo")
def _repo_fixture(*, tmp_path: Path) -> Path:
    """A target repo carrying the plan thread, and no sessions anywhere."""
    repo = tmp_path / "repo"
    (repo / "plan" / _TOPIC).mkdir(parents=True)
    return repo


def _fake_agent(*, tmp_path: Path) -> Path:
    """An executable literally NAMED `claude`, so `ps` reports a real agent."""
    script = tmp_path / "claude"
    script.write_text("#!/bin/sh\nsleep 300\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def test_the_prose_partitions_all_five_preconditions_by_name() -> None:
    """ACCEPTANCE LEG 4 — exhaustive, and each name in EXACTLY ONE phase.

    Three readings must agree: the declared phase table, the section each
    precondition's commands actually live under, and this module's own pinned
    map. A check that drifts into both phases re-creates the ordering inversion
    for itself; one that drifts out of both has been lost in the move.

    Sabotage that reddens this: move precondition 4's block under `### Drive
    phase`, or drop a row from the prose's phase table.
    """
    units = _units()
    assert sorted(name for _, name, _ in units) == sorted(_EXPECTED_PHASE)
    assert {name: phase for phase, name, _ in units} == _EXPECTED_PHASE
    assert {
        match.group("name"): match.group("phase") for match in _TABLE_ROW.finditer(_section())
    } == _EXPECTED_PHASE


def test_every_precondition_still_supplies_exactly_one_runnable_command() -> None:
    """A precondition that states a requirement and supplies no command is the
    defect the contract already refused. The split must not have dropped one."""
    assert {name: len(_blocks(body=body)) for _, name, body in _units()} == dict.fromkeys(
        _EXPECTED_PHASE, 1
    )


def test_a_charter_is_authorable_for_a_thread_with_no_tmux_sessions_at_all(
    *, repo: Path, tmp_path: Path
) -> None:
    """ACCEPTANCE LEG 1 — driven end to end, with no tmux BINARY at all.

    Stronger than "no sessions": the authoring gate runs on a PATH holding
    nothing, so it cannot be passing because some tmux happened to answer. The
    plan directory is the whole gate, which is the ruling.
    """
    empty = tmp_path / "nothing"
    empty.mkdir()
    assert shutil.which("tmux", path=str(empty)) is None
    scripts = _scripts_by_name(repo=repo)
    result = _run(script=scripts["plan-directory-exists"], path=str(empty), cwd=repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "HALT" not in result.stdout


def test_the_authoring_gate_itself_still_halts_when_the_plan_is_absent(*, tmp_path: Path) -> None:
    """THE CONTROL for the leg above, and it is not optional.

    A gate that passed unconditionally would satisfy that test too. The artifact
    check must still refuse a topic whose plan directory does not exist.
    """
    empty = tmp_path / "nothing"
    empty.mkdir()
    absent = tmp_path / "no-such-repo"
    absent.mkdir()
    result = _run(
        script=_scripts_by_name(repo=absent)["plan-directory-exists"],
        path=str(empty),
        cwd=absent,
    )

    assert result.returncode == 1
    assert f"HALT: missing plan {absent}/plan/{_TOPIC}" in result.stdout
    assert "REMEDY: create or choose the correct plan topic before supervising" in result.stdout


def test_every_drive_check_still_halts_with_its_exact_message_and_expected_name(
    *, repo: Path, tmp_path: Path, tmux_path: str, socket: str
) -> None:
    """ACCEPTANCE LEG 2 — THE LOAD-BEARING ONE.

    The four live-session checks run against a tmux server with no sessions in
    it. Each must still HALT, name its own failing check, and name the exact
    session it expected — byte for byte the messages the pre-split gate emitted.

    Sabotage that reddens this: reword any HALT or REMEDY line in the drive
    phase, or let a drive check exit 0 when its session is missing.
    """
    _fake_agent(tmp_path=tmp_path)
    scripts = _scripts_by_name(repo=repo)
    verdicts = {}
    for name, (halt, remedy) in _DRIVE_HALT.items():
        result = _run(script=scripts[name], path=tmux_path, cwd=repo)
        verdicts[name] = (result.returncode, halt in result.stdout, remedy in result.stdout)

    assert verdicts == dict.fromkeys(_DRIVE_HALT, (1, True, True))
    # ACCEPTANCE LEG 3, proved BEHAVIOURALLY rather than by reading the prose:
    # four gates just failed and not one of them left a session behind.
    assert _tmux_on(socket, "list-sessions").returncode != 0


def test_the_control_every_drive_check_passes_against_a_live_rigged_pair(
    *, repo: Path, tmp_path: Path, tmux_path: str, socket: str
) -> None:
    """THE POSITIVE CONTROL. Without it a gate that always HALTs passes leg 2.

    Both sessions hold a process literally named `claude`, and the worker's pane
    sits inside the target repo — the state the drive phase exists to certify.
    Each check must not merely exit 0 but PRINT its own evidence, because a block
    that does nothing also exits 0.
    """
    agent = str(_fake_agent(tmp_path=tmp_path))
    # The agent is the PANE COMMAND, not something typed in afterwards: a
    # `send-keys` rig races its own `ps`, and a leg that flakes on host load is
    # worse than no leg. `-c` puts the worker's pane cwd inside the repo, which
    # is what precondition 5 certifies.
    _tmux_on(socket, "new-session", "-d", "-s", _WORKER, "-c", str(repo), agent)
    _tmux_on(socket, "new-session", "-d", "-s", _SUPERVISOR, "-c", str(tmp_path), agent)
    live = wait_for_pane_current_path(
        tmux=lambda *args: _tmux_on(socket, *args), target=f"={_WORKER}:", expected=repo
    )
    assert live == str(repo)

    scripts = _scripts_by_name(repo=repo)
    verdicts = {}
    for name, evidence in _DRIVE_PASS_EVIDENCE.items():
        result = _run(script=scripts[name], path=tmux_path, cwd=repo)
        verdicts[name] = (result.returncode, evidence in result.stdout)

    assert verdicts == dict.fromkeys(_DRIVE_PASS_EVIDENCE, (0, True))


def test_nothing_in_either_phase_fabricates_the_state_its_gate_asks_about() -> None:
    """ACCEPTANCE LEG 3, asserted explicitly rather than assumed to have survived.

    Manufacturing state to pass a HALT check is the boundary the original live
    exercise respected, and splitting the checks is not permission to relax it.
    Both halves are pinned: no emitted command may CREATE a session, and the
    refusal sentence itself must still stand in the drive phase.
    """
    blocks = "\n".join(_blocks(body=_section()))
    assert {verb: verb in blocks for verb in _FABRICATING_VERBS} == dict.fromkeys(
        _FABRICATING_VERBS, False
    )
    assert _NO_FABRICATION_RULE in _phase_bodies()["drive"]


def test_a_binder_authored_with_no_session_still_carries_the_whole_drive_gate() -> None:
    """ACCEPTANCE LEG 5 — authoring earlier must not produce a degraded binder.

    The generator must instruct the binder to reproduce the DRIVE-phase commands
    verbatim, and the shared role layer a cold-open supervisor reads alongside it
    must describe the same four as its drive gate. A binder authored before any
    session existed is then indistinguishable from one authored beside a running
    pair.
    """
    prose = _PROSE.read_text(encoding="utf-8")
    assert "REPRODUCE the four DRIVE-PHASE precondition commands above verbatim" in prose
    assert "The authoring-phase check is NOT reproduced here." in prose
    shared = _SHARED_LAYER.read_text(encoding="utf-8")
    assert "These four are the DRIVE-phase preconditions." in shared
    assert "is a full binder, not a\ndegraded one" in shared


def test_the_recorded_workaround_is_retired_from_the_plan_prose() -> None:
    """ACCEPTANCE LEG 6. The recipe existed only to invert the authoring order.

    Left standing it would tell the next author to stand up two sessions before
    authoring a charter — the inversion this item removes, restored by hand. The
    retirement note is the POSITIVE CONTROL: it proves this scan reaches the plan
    records at all, so the absence above is a finding rather than an empty glob.
    """
    records = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(_REPO_ROOT.glob("plan/**/*.md"))
    )
    assert _RETIRED_PRESCRIPTION not in records
    assert _RETIREMENT_NOTE in records
    assert _RETIREMENT_NOTE in _WORKAROUND_RECORD.read_text(encoding="utf-8")
