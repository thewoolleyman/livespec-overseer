"""The Codex-on-Herdr lifecycle controller, driven against a REAL herdr instance.

This is the in-sandbox half of `overseer-uzvcbn.4`. The host-captured half -- the
same controller against an AUTHENTICATED Codex under
`scripts/overseer-live-exercise.sh` -- is a release-host obligation and is NOT
discharged here; what these exercises prove is that the controller drives the
shipped mechanics correctly when the only thing stubbed is the agent binary.

**Everything except Codex is real.** A genuine `herdr --session <unique> server`,
a genuine pane, the `overseerd` the shipped `overseer-start` resolves and launches
from the run's own disposable runtime prefix, the real mapping store, the real
injection-stamp sidecar and the real `/proc`-backed Codex discovery join. The
agent is `tests/stub_codex.py`, which implements only the surfaces the shipped
code reads -- `comm`, a held rollout fd, a `session_index.jsonl` record on
`/rename`, and a pane frame `signals.py` parses. Nothing in the daemon is
patched, seamed or faked.

**The expensive run happens ONCE, inside one test, deliberately.** The full arc
takes minutes, and this suite runs under `pytest -n <workers>` with the default
per-test distribution, so a module-scoped fixture would be re-entered by every
worker that drew a test from this file -- paying the whole arc two or three times
over. The acceptance facts that share a run are therefore asserted together, each
with its own message, rather than split into one test per fact that would each pay
for its own daemon.

**The host condition travels with the run.** The lifecycle run happens with
unrelated `codex`-named processes live outside its scratch root (see
`outside_codex_processes`), because the defect this exercise failed to survive
was host leakage: Codex identity came from a host-wide `/proc` scan that nothing
scoped, so the exercise daemon read the operator's real sessions beside its stub
(work-item `overseer-crjbmp`). The factory runs no Codex of its own, which is
precisely why CI stayed green while every push from the release host failed.

**The second half of that host condition is the operator shell's own TERMINAL,
and it is the one that actually broke the run** (work-item `overseer-4mdi2g`).
The release host's operator shell runs INSIDE the fleet herdr session, so every
`HERDR_*` variable herdr injects into that pane is in this test process's
environment — and the exercise used to copy the whole environment into the
server it starts and the pane that server spawns. `operator_pane_environment`
stages those variables here as unmistakable DECOYS and
`_scrub_terminal_owner_env` removes them from everything the exercise starts, so
the exercise declares the one coordinate it owns and inherits none. See
`_DECOY_PANE_ENVIRONMENT` for which inherited value was decisive and what it did
to the run.

**Session isolation is herdr's own `--session` mechanism**, and the exercise
additionally runs under a scratch `HOME` holding its own daemon runtime prefix, so
the mapping store, the stamp sidecar, the watch declaration, the Codex index and
the installed `overseerd` are all disposable. The operator's own daemon, store,
runtime prefix and sessions are never addressed -- see `_scratch_home` for the
measured defect that rule is written against.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import herdr_identity
import pytest
from herdr_live_server import raw_request, require_herdr, start_server, stop_server, unique_session

from overseer import runtime_prefix

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROLLER = REPO_ROOT / "scripts" / "overseer-live-exercise-codex-herdr.sh"
VERIFIER = REPO_ROOT / "scripts" / "overseer_live_exercise_evidence.py"

REQUIRED_STAGES = (
    "bootstrap",
    "adoption",
    "wrap-up",
    "declaration",
    "replacement",
    "continuation",
)
TOPIC = "exercise-topic"
PASSING_RUN_TIMEOUT = 1500.0
NEVER_IDLE_RUN_TIMEOUT = 600.0
# A Unix socket address is bounded at ~108 bytes, and herdr derives
# `<home>/.config/herdr/sessions/<session>/herdr-client.sock` from the HOME the
# exercise runs under. Rooting that at pytest's own `tmp_path` overruns the bound
# before the server can bind -- measured, and it surfaces as the server exiting
# with `local socket name length exceeds capacity of sun_path`, which names the
# socket rather than the directory that made it long. So the exercise gets a SHORT
# root of its own, and the session label stays short for the same reason.
_SHORT_ROOT_PREFIX = "ovx-"
_SESSION_LABEL = "cx"
# The release host runs the operator's own authenticated Codex sessions beside this
# exercise, and the exercise used to read them: Codex identity came from a host-wide
# `/proc` scan that nothing scoped (work-item `overseer-crjbmp`). The factory runs none
# by itself, which is exactly why CI and the factory stayed green while every push from
# the release host failed -- so the exercise now brings the host condition with it.
# Seven is the count measured on the release host 2026-10-22 (`pgrep -c codex`).
_OUTSIDE_CODEX_PROCESSES = 7
_OUTSIDE_ROOT_PREFIX = "ovx-operator-"
_OUTSIDE_READY_TIMEOUT = 30.0
_OUTSIDE_STOP_TIMEOUT = 10.0
_OUTSIDE_POLL_SECONDS = 0.1
# The daemon-owned runtime prefix, relative to HOME. `overseer-start` provisions
# `<HOME>/.local/share/livespec-overseer/runtime/<version>`, and the venv it builds
# there bakes that ABSOLUTE path into its own interpreter shebang -- which is why a
# scratch HOME must never resolve this path onto the operator's own prefix.
_RUNTIME_PREFIX_RELATIVE = Path(".local") / "share" / "livespec-overseer"
_DAEMON_HELP_TIMEOUT = 60.0
# A console script whose own absolute path overruns the kernel's shebang bound is
# written with a portable `#!/bin/sh` wrapper that execs the interpreter from its
# second line. See `_interpreter_of`.
_PORTABLE_SHEBANG_SHELLS = frozenset({"sh", "bash"})
_PORTABLE_SHEBANG_EXEC = re.compile(r"^'''exec' '([^']+)'")
# The pane the controller drives (`AGENT_PANE` in
# `scripts/overseer-live-exercise-codex-herdr.sh`). It is a POSITION, not a lookup: the
# controller creates one workspace on a server it expects to be empty and addresses
# that workspace's root pane, so anything which makes the server open a workspace
# FIRST hands the controller a stray pane instead -- silently, because the pane it
# gets is a perfectly good pane.
AGENT_PANE = "w1:p1"
# The operator shell's inherited herdr pane environment, as measured on the release
# host 2026-10-22 at ebccbc7d (`HERDR_PANE_ID=w5:p5`, `HERDR_WORKSPACE_ID=w5`,
# `HERDR_ENV=1`, `HERDR_SOCKET_PATH=~/.config/herdr/herdr.sock`, plus `HERDR_TAB_ID`,
# `HERDR_BIN_PATH` and `HERDR_STARTUP_CWD`).
#
# `HERDR_STARTUP_CWD` is the decisive one. Herdr sets it on the panes it relaunches
# when it restores a session, and a server that INHERITS it opens a startup workspace
# of its own: measured here, `pane.list` answers `w1:p1` before any workspace is
# created and the controller's own `workspace.create` returns `w2`. So `AGENT_PANE`
# addressed the startup pane, which is rooted in the operator's startup cwd rather
# than the watched exercise repo. Codex came up there, `/rename` indexed a rollout
# there and `overseer-start` brought the daemon up there, so BOOTSTRAP PASSED -- and
# then nothing adopted the track, because adoption requires the session's cwd to
# resolve inside a watched repo. The daemon's snapshot row carried `tmux: null` and
# `restart_model.reason: pane-absent`, and the run reported it as the ADOPTION stage
# failing on Codex identity, which is why `overseer-crjbmp` chased a /proc-scoping
# hypothesis that was not the host's cause.
#
# These values are DECOYS: each one names an instance that does not exist, so a
# server or pane that reached one would fail rather than quietly address something
# real. They are set in the TEST PROCESS, which is where the release host's leak
# begins.
_DECOY_PANE_ENVIRONMENT: dict[str, str] = {
    # Deliberately NOT the host's literal `1`: herdr sets `HERDR_ENV=1` on the
    # exercise's OWN panes too, so a truthful `1` would be indistinguishable from the
    # value the exercise is entitled to, and an assertion over observed environments
    # could not tell a leak from a legitimate injection.
    "HERDR_ENV": "ovx-decoy-env",
    "HERDR_PANE_ID": "w5:p5",
    "HERDR_TAB_ID": "w5:t5",
    "HERDR_WORKSPACE_ID": "w5",
    "HERDR_SESSION": "ovx-decoy-operator-session",
    "HERDR_SOCKET_PATH": "/ovx-decoy/operator/herdr.sock",
    "HERDR_STARTUP_CWD": "/ovx-decoy/operator-startup-cwd",
    "HERDR_BIN_PATH": "/ovx-decoy/bin/herdr",
    "TMUX": "/ovx-decoy/tmux-default,1,0",
    "TMUX_PANE": "%5",
}
# What the scrub removes. A PREFIX rather than a list, because a list is what failed:
# `scripts/overseer-live-exercise.sh` unsets seven `HERDR_*` names by hand and misses
# `HERDR_STARTUP_CWD` -- the only one that changed the outcome.
_TERMINAL_OWNER_PREFIXES = ("HERDR_",)
_TERMINAL_OWNER_NAMES = frozenset({"TMUX", "TMUX_PANE"})


@pytest.fixture
def short_root() -> Iterator[Path]:
    """A disposable root short enough for a herdr socket address to fit under it."""
    root = Path(tempfile.mkdtemp(prefix=_SHORT_ROOT_PREFIX))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def operator_pane_environment(*, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """This test process AS IT IS ON THE RELEASE HOST: inside the fleet herdr session.

    The factory has no herdr parent, so it never carried these variables at all --
    which is exactly why CI, the factory and `overseer-crjbmp`'s decoy-process proof
    were green while every push from the release host failed. Staging them here moves
    the leak to where it can be gated.

    The suite-wide `_isolate_ambient_herdr` fixture scrubs `HERDR_SOCKET_PATH` from
    every test process, so that one is re-declared here rather than merely left alone.
    """
    for name, value in _DECOY_PANE_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    return dict(_DECOY_PANE_ENVIRONMENT)


def _scrub_terminal_owner_env(*, env: dict[str, str]) -> dict[str, str]:
    """Drop every inherited terminal-owner selector from a child's environment.

    The exercise owns its own herdr instance and declares the ONE coordinate it wants
    (`HERDR_SOCKET_PATH`, taken from the server it just started). Every other value a
    parent terminal injected describes a DIFFERENT instance, and the server, the pane
    shell and the daemon `overseer-start` launches all read these names -- so an
    inherited value is not inert. See `_DECOY_PANE_ENVIRONMENT` for the measured
    consequence of carrying one.
    """
    return {
        key: value
        for key, value in env.items()
        if not key.startswith(_TERMINAL_OWNER_PREFIXES) and key not in _TERMINAL_OWNER_NAMES
    }


def _environ_of(*, pid: int) -> tuple[str, ...]:
    """`pid`'s own environment as `KEY=value` entries, read from `/proc`.

    The process's environment as the KERNEL holds it, which is the only reading that
    can answer what a child actually inherited. Asserting over the dict this module
    assembled would prove the scrub was called, not that it reached anything.
    """
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return ()
    return tuple(entry.decode(errors="replace") for entry in raw.split(b"\0") if entry)


def _pane_shell_pid(*, socket_path: str, pane_id: str) -> int:
    """The retained shell of `pane_id` on this server, or 0 when it cannot be read.

    Through a raw request rather than the shipped adapter: this is control evidence
    about the exercise's own pane, and taking it from the surface under test would
    only prove the adapter is self-consistent.
    """
    reply = raw_request(
        socket_path=socket_path, method="pane.process_info", params={"pane_id": pane_id}
    )
    result = reply.get("result")
    info = result.get("process_info") if isinstance(result, dict) else None
    shell = info.get("shell_pid") if isinstance(info, dict) else None
    return shell if isinstance(shell, int) else 0


def _inherited_decoys(*, observed: tuple[str, ...], decoys: Mapping[str, str]) -> list[str]:
    """Every observed `KEY=value` entry that is one of `decoys` verbatim."""
    pairs = (entry.split("=", 1) for entry in observed if "=" in entry)
    return [f"{name}={value}" for name, value in pairs if decoys.get(name) == value]


def _codex_named_pids(*, processes: list[subprocess.Popen[bytes]]) -> list[int]:
    """Which of these processes are live and present as `codex` in `/proc`."""
    return [
        process.pid
        for process in processes
        if process.poll() is None
        and Path(f"/proc/{process.pid}/comm").read_text(encoding="utf-8").strip() == "codex"
    ]


@pytest.fixture
def outside_codex_processes() -> Iterator[list[subprocess.Popen[bytes]]]:
    """Unrelated `codex`-named processes, running OUTSIDE this run's scratch root.

    This is the release host's condition, brought into the factory. They are started
    BEFORE the controller and proven present as `codex` in `/proc` before the run
    begins, because a decoy that failed to rename itself would leave the exercise
    passing for the reason it always passed here -- no second Codex world on the host --
    and prove nothing about the one the operator actually runs.

    Their root is its own temporary directory rather than a child of `short_root`, so
    "outside the test's scratch root" is literally where they live, including their
    `HOME`, their `CODEX_HOME`, their cwd and every rollout they hold.
    """
    root = Path(tempfile.mkdtemp(prefix=_OUTSIDE_ROOT_PREFIX))
    started: list[subprocess.Popen[bytes]] = []
    try:
        home = root / "operator-home"
        codex_home = home / ".codex"
        codex_home.mkdir(parents=True)
        launcher = root / "operator-codex.py"
        _write_executable(
            path=launcher,
            body=_OUTSIDE_CODEX_LAUNCHER.format(tests_dir=str(Path(__file__).resolve().parent)),
        )
        environment = _scrub_coverage_env(env=dict(os.environ))
        environment["HOME"] = str(home)
        environment["CODEX_HOME"] = str(codex_home)
        for index in range(_OUTSIDE_CODEX_PROCESSES):
            started.append(
                subprocess.Popen(  # noqa: S603 - a launcher this fixture just wrote
                    [sys.executable, str(launcher), str(uuid.uuid4()), f"operator-topic-{index}"],
                    cwd=str(home),
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        deadline = time.monotonic() + _OUTSIDE_READY_TIMEOUT
        while time.monotonic() < deadline:
            if len(_codex_named_pids(processes=started)) == _OUTSIDE_CODEX_PROCESSES:
                break
            time.sleep(_OUTSIDE_POLL_SECONDS)
        assert len(_codex_named_pids(processes=started)) == _OUTSIDE_CODEX_PROCESSES, (
            f"only {len(_codex_named_pids(processes=started))} of "
            f"{_OUTSIDE_CODEX_PROCESSES} decoy processes came up as `codex`, so this run "
            "would not reproduce the release host's condition"
        )
        yield started
    finally:
        for process in started:
            process.terminate()
        for process in started:
            with contextlib.suppress(subprocess.TimeoutExpired):
                _ = process.wait(timeout=_OUTSIDE_STOP_TIMEOUT)
        shutil.rmtree(root, ignore_errors=True)


# The stub reaches the checkout by path rather than by install: it is test
# infrastructure, and putting it on the exercise's `PYTHONPATH` would also put it
# where the shipped modules resolve from.
_STUB_LAUNCHER = """#!/usr/bin/env python3
import os
import sys

{environment}
sys.path.insert(0, {tests_dir!r})

import stub_codex

raise SystemExit(stub_codex.main())
"""

# One unrelated `codex`-named process, standing in for a session of the operator's own.
# It presents the surfaces the shipped Codex join reads -- `comm`, a HELD rollout fd and
# a `session_index.jsonl` record naming it -- and every path it names is in its OWN Codex
# world outside this run's scratch root, which is the whole point: that is the shape the
# exercise daemon must not read. `stub_codex`'s helpers are reused rather than re-derived,
# so the decoy cannot drift from the surfaces the stub itself presents.
#
# The DESCENDANT shape -- a 0.16x carrier holding no rollout while a shared app-server
# holds it -- is covered deterministically instead, by
# `tests/test_codex_adoption_scoped_to_the_daemons_codex_home.py`; it needs a process
# tree this fixture has no reason to build.
_OUTSIDE_CODEX_LAUNCHER = """#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, {tests_dir!r})

import stub_codex

stub_codex.set_process_name()
home = Path(os.environ["CODEX_HOME"])
session_id, thread_name = sys.argv[1], sys.argv[2]
rollout = stub_codex.rollout_path(
    home=home, session_id=session_id, now=datetime.now(tz=timezone.utc)
)
rollout.parent.mkdir(parents=True, exist_ok=True)
held = rollout.open("a", encoding="utf-8")
try:
    with (home / "session_index.jsonl").open("a", encoding="utf-8") as index:
        _ = index.write(json.dumps({{"id": session_id, "thread_name": thread_name}}) + "\\n")
    while True:
        time.sleep(3600)
finally:
    held.close()
"""

# Logs the FULL argv of every herdr invocation, then execs the real binary so the
# controller's own behaviour is unchanged. This is how "every herdr command
# carries `--session`" becomes an OBSERVATION of the commands actually issued
# rather than a grep over the script's source, which could not see a command
# assembled at runtime.
_HERDR_SHIM = """#!/usr/bin/env bash
printf '%s\\n' "$*" >>{log!r}
exec {real_herdr!r} "$@"
"""


@dataclass(frozen=True, kw_only=True)
class ExerciseRun:
    """One completed controller run and everything it left behind."""

    completed: subprocess.CompletedProcess[str]
    evidence: Path
    herdr_log: Path
    home: Path
    socket_path: str
    server_environ: tuple[str, ...]
    pane_shell_environ: tuple[str, ...]

    def snapshot_row(self, *, topic: str) -> dict[str, object]:
        """The exercise DAEMON's own status row for `topic`, or an empty row.

        The daemon writes `~/.livespec-overseer-status.json` under the run's scratch
        HOME, so this is the daemon's answer about the track rather than the
        controller's -- the same file the controller's own stage predicates read.
        """
        snapshot = self.home / ".livespec-overseer-status.json"
        if not snapshot.is_file():
            return {}
        parsed: object = json.loads(snapshot.read_text(encoding="utf-8"))
        rows = parsed.get("rows", []) if isinstance(parsed, dict) else []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get("topic") == topic:
                return row
        return {}

    def records(self) -> list[dict[str, str]]:
        """Every lifecycle record, in the order the controller appended them."""
        lifecycle = self.evidence / "lifecycle.jsonl"
        if not lifecycle.is_file():
            return []
        return [
            json.loads(line)
            for line in lifecycle.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def herdr_commands(self) -> list[str]:
        """Every herdr argv the controller issued, as logged by the shim."""
        if not self.herdr_log.is_file():
            return []
        return [
            line for line in self.herdr_log.read_text(encoding="utf-8").splitlines() if line.strip()
        ]


def _checked_in_verifier() -> Callable[..., int]:
    """`scripts/overseer_live_exercise_evidence.py`'s own `main`, loaded from the script.

    Loaded BY PATH rather than imported from `overseer.live_exercise_evidence`, so
    this exercises the checked-in CLI binding -- including the `sys.path` insertion
    that lets it resolve the package from outside the checkout -- and not just the
    module behind it. Called in process because an instrumented Python child races
    `COVERAGE_PROCESS_START`; the script's `__main__` is `raise SystemExit(main())`,
    so `main`'s return value IS the exit status the acceptance criterion names.
    """
    spec = importlib.util.spec_from_file_location("checked_in_evidence_verifier", VERIFIER)
    assert spec is not None and spec.loader is not None, f"cannot load {VERIFIER}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def _scratch_home(*, root: Path) -> Path:
    """A disposable HOME carrying its OWN daemon runtime, plus the warm uv cache.

    `~/.cache` is symlinked because `uv` keys its cache off HOME and a cold one
    rebuilds the whole environment -- documented in `overseer/AGENTS.md` as looking
    exactly like a daemon hang.

    `~/.local/share/livespec-overseer` is deliberately NOT symlinked, and that is
    the whole shape of this helper. It used to be, so `overseer-start` could reuse
    an already-provisioned daemon runtime prefix -- but a link is not read-only. On
    a host with no prefix for the checkout's version the FIRST run provisioned one
    through it, and the venv baked the scratch path into its own interpreter
    (measured 2026-10-22: `runtime/5.33.8/venv/bin/overseerd` carried the shebang
    `#!/tmp/ovx-vm170k6z/home/.local/share/livespec-overseer/runtime/5.33.8/venv/bin/python`).
    The scratch root is deleted at teardown, so the host's shared prefix was left
    with a dead interpreter and every later bootstrap there -- the exercise's and
    the operator's alike -- failed with `bad interpreter`. The exercise builds its
    own prefix inside the root instead.
    """
    home = root / "home"
    (home / ".local" / "share").mkdir(parents=True)
    cache = Path.home() / ".cache"
    if cache.exists():
        (home / ".cache").symlink_to(cache)
    _ = _provision_daemon_runtime(home=home)
    return home


def _provision_daemon_runtime(*, home: Path) -> Path:
    """Install this checkout's `overseerd` into the scratch HOME's own runtime prefix.

    `runtime_prefix.ensure_runtime` short-circuits on an existing executable, so
    filling the version-keyed prefix here is what keeps the shipped `overseer-start`
    from provisioning a runtime of its own -- the step that used to reach outside
    the scratch root. The install source is this CHECKOUT rather than the release
    tag the daemon would otherwise fetch from git: it is the build under test, it
    needs no network, and it is installed NON-EDITABLY exactly as the released path
    installs, so the daemon still runs an installed distribution and never the
    working tree.
    """
    prefix = runtime_prefix.runtime_prefix(home=home)
    daemon = runtime_prefix.ensure_runtime(prefix=prefix, install_source=str(REPO_ROOT))
    assert daemon is not None, f"could not provision an exercise daemon runtime under {prefix}"
    return daemon


def _write_executable(*, path: Path, body: str) -> None:
    _ = path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _exercise_bin(*, root: Path, never_idle: bool) -> tuple[Path, Path]:
    """A bin directory holding the stub `codex` and the logging `herdr` shim."""
    binaries = root / "bin"
    binaries.mkdir()
    real_herdr = shutil.which("herdr")
    assert real_herdr is not None, "require_herdr() should already have skipped"
    environment = 'os.environ["STUB_CODEX_NEVER_IDLE"] = "1"' if never_idle else ""
    _write_executable(
        path=binaries / "codex",
        body=_STUB_LAUNCHER.format(
            environment=environment, tests_dir=str(Path(__file__).resolve().parent)
        ),
    )
    herdr_log = root / "herdr-commands.log"
    _write_executable(
        path=binaries / "herdr",
        body=_HERDR_SHIM.format(log=str(herdr_log), real_herdr=real_herdr),
    )
    return binaries, herdr_log


def _scrub_coverage_env(*, env: dict[str, str]) -> dict[str, str]:
    """Drop the settings that make a Python child self-instrument under `--cov`.

    pytest-cov arms `pytest-cov.pth` through `COV_CORE_SOURCE`, so EVERY Python
    process reachable from this environment measures itself -- and this exercise
    starts several: the stub `codex` through its launcher, the successor the herdr
    SERVER spawns, and each `shipped()` predicate the controller runs. Two
    consequences, both measured elsewhere in this suite: concurrent children race
    the data file, and `tests/stub_codex.py` enters the coverage denominator at
    partial coverage, failing the per-file 100% floor for a file that is the
    exercise's disposable agent double rather than code under test. Scrubbing is
    the repo-wide idiom for a spawned Python child (see `test_pre_commit_gate_
    shape.py`, `tests/integration/test_shipped_launcher_plugin_package.py`), and
    it leaves every coverage gate exactly as strict as it was.
    """
    return {
        key: value
        for key, value in env.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }


def _run_controller(*, root: Path, never_idle: bool, timeout: float) -> ExerciseRun:
    """Start one exercise herdr instance and drive the controller against it."""
    require_herdr()
    home = _scratch_home(root=root)
    binaries, herdr_log = _exercise_bin(root=root, never_idle=never_idle)
    evidence = root / "evidence"
    evidence.mkdir()

    # The server runs under the scratch HOME so its socket, its session registry
    # and everything the controller writes share one disposable root. The
    # terminal-owner scrub is what keeps a test process that is ITSELF inside a herdr
    # pane from lending its coordinates to the instance this run owns.
    environment = _scrub_terminal_owner_env(env=_scrub_coverage_env(env=dict(os.environ)))
    environment["HOME"] = str(home)
    # A Herdr replacement is spawned by the SERVER, not by the controller's
    # original pane shell.  Give that server the scratch Codex home before it
    # starts, otherwise the initial stub (whose shell is later exported below)
    # and its successor write rollouts to different indexes.
    environment["CODEX_HOME"] = str(home / ".codex")
    environment["PATH"] = f"{binaries}{os.pathsep}{environment['PATH']}"
    session = unique_session(label=_SESSION_LABEL)
    previous_home = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        server = start_server(scratch=root / "server", session=session, env=environment)
        # Read while the server is certainly alive. A process's environment is fixed
        # at `exec`, so this reading is its whole life's environment.
        server_environ = _environ_of(pid=server.server_pid)
        environment["HERDR_SOCKET_PATH"] = server.socket_path
        environment.update(
            {
                "OVERSEER_EXERCISE_BACKEND": "herdr",
                "OVERSEER_EXERCISE_INSTANCE": session,
                "OVERSEER_EXERCISE_TOPIC": TOPIC,
                "OVERSEER_EXERCISE_EVIDENCE": str(evidence),
                "OVERSEER_EXERCISE_REPO": str(root / "repo"),
            }
        )
        try:
            completed = subprocess.run(  # noqa: S603 - the checked-in controller, fixed argv
                [str(CONTROLLER)],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=environment,
                cwd=str(root),
            )
            # The retained shell of the controller's pane outlives the controller, so
            # what it inherited is still readable here -- and it has to be read before
            # the server is stopped, because stopping the server takes the pane with it.
            pane_shell_environ = _environ_of(
                pid=_pane_shell_pid(socket_path=server.socket_path, pane_id=AGENT_PANE)
            )
        finally:
            stop_server(session=session)
    finally:
        if previous_home is None:  # pragma: no cover - HOME is always set on this host
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = previous_home
    return ExerciseRun(
        completed=completed,
        evidence=evidence,
        herdr_log=herdr_log,
        home=home,
        socket_path=server.socket_path,
        server_environ=server_environ,
        pane_shell_environ=pane_shell_environ,
    )


def test_the_controller_is_a_checked_in_executable() -> None:
    """The exercise coordinator runs this by path, so the bit is part of shipping it."""
    assert CONTROLLER.is_file(), f"the controller is missing from the repository: {CONTROLLER}"
    assert os.access(CONTROLLER, os.X_OK), f"the controller is not executable: {CONTROLLER}"


def test_backend_starts_after_the_scratch_home_has_a_zshrc() -> None:
    """A zsh pane must not consume the exercise input with its first-run menu."""
    inside = (REPO_ROOT / "scripts" / "overseer-live-exercise-inside.sh").read_text(
        encoding="utf-8"
    )

    zshrc_seed = ': >"$HOME/.zshrc"'
    backend_start = 'if [[ "$backend" == herdr ]]; then\n  herdr --session "$instance" server'
    assert zshrc_seed in inside
    assert inside.index(zshrc_seed) < inside.index(backend_start)


def test_bootstrap_failure_keeps_launcher_output_and_elapsed_time() -> None:
    """A loaded-host bootstrap expiry must identify the launcher that did not finish."""
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "readonly DAEMON_TIMEOUT=600" in controller
    assert "bootstrap_started_at=$SECONDS" in controller
    assert '"$evidence/overseer-start.log"' in controller
    assert 'tail -n 3 -- "$overseer_start_output"' in controller
    assert "after ${elapsed}s" in controller


def test_the_scratch_home_never_writes_through_to_the_hosts_runtime_prefix(
    short_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing this exercise provisions may land under the operator's own prefix.

    The scratch HOME used to SYMLINK `~/.local/share/livespec-overseer` so a run
    could reuse an already-provisioned daemon runtime. A link is not read-only: on
    a host with no prefix for the checkout's version the first run provisioned one
    THROUGH it, into the operator's tree.
    """
    host = _host_home(root=tmp_path, monkeypatch=monkeypatch)

    home = _scratch_home(root=short_root)

    scratch_prefix = home / _RUNTIME_PREFIX_RELATIVE
    assert not scratch_prefix.is_symlink(), (
        "the scratch HOME symlinks the operator's shared daemon runtime prefix, so "
        "everything the exercise provisions is written into the host's own tree"
    )
    (scratch_prefix / "runtime" / "write-through-probe").mkdir(parents=True, exist_ok=True)
    assert not (
        host / _RUNTIME_PREFIX_RELATIVE / "runtime" / "write-through-probe"
    ).exists(), "a directory created under the scratch HOME appeared under the host's prefix"
    assert (home / ".cache").is_symlink(), (
        "the warm `uv` cache link is what keeps a run from rebuilding its whole "
        "environment; only the daemon runtime prefix is supposed to stop being shared"
    )


def test_two_consecutive_runs_each_get_their_own_usable_daemon_runtime(
    short_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deleted run's scratch root cannot leave the next run without a daemon.

    The SECOND run is the one that failed on the release host: the first run's venv
    had baked its own scratch path into the shared prefix's interpreter, the scratch
    root was deleted at teardown, and every later bootstrap died with `bad
    interpreter` -- reported only as `overseer-start did not bring a daemon up`.
    """
    _ = _host_home(root=tmp_path, monkeypatch=monkeypatch)

    for index in (1, 2):
        root = short_root / f"run-{index}"
        daemon = _daemon_executable(home=_scratch_home(root=root))
        assert daemon.is_file(), f"run {index} provisioned no daemon runtime at {daemon}"
        completed = subprocess.run(  # noqa: S603 - the runtime this run just provisioned
            [str(daemon), "--help"],
            capture_output=True,
            text=True,
            timeout=_DAEMON_HELP_TIMEOUT,
            check=False,
            env=_scrub_coverage_env(env=dict(os.environ)),
        )
        assert completed.returncode == 0, (
            f"run {index}'s daemon runtime does not execute (exit "
            f"{completed.returncode}): {completed.stderr.strip()}"
        )
        shutil.rmtree(root)


def test_a_finished_run_leaves_no_interpreter_path_behind_in_the_host_prefix(
    short_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once a run's scratch root is gone, no surviving runtime may point into it.

    This is the host-visible damage the defect left: `runtime/5.33.8/venv/bin/overseerd`
    carrying the shebang
    `#!/tmp/ovx-vm170k6z/home/.local/share/livespec-overseer/runtime/5.33.8/venv/bin/python`,
    a path deleted the moment the exercise finished.
    """
    host = _host_home(root=tmp_path, monkeypatch=monkeypatch)
    root = short_root / "run"
    daemon = _daemon_executable(home=_scratch_home(root=root))
    assert daemon.is_file(), f"the run provisioned no daemon runtime at {daemon}"
    interpreter = _interpreter_of(executable=daemon)
    assert str(root) in interpreter, (
        "the run's own runtime is not rooted in its scratch tree, so this test cannot "
        f"say anything about what the run leaves behind: {interpreter}"
    )

    shutil.rmtree(root)  # the run has ended; `short_root` deletes exactly this tree.

    poisoned = [
        str(script)
        for script in (host / _RUNTIME_PREFIX_RELATIVE).rglob("venv/bin/overseerd")
        if str(root) in _interpreter_of(executable=script)
    ]
    assert not poisoned, (
        "the host's daemon runtime prefix carries an interpreter inside the finished "
        f"run's deleted scratch root, so the next bootstrap there cannot start: {poisoned}"
    )


@pytest.mark.integration
def test_a_stub_codex_run_records_every_lifecycle_stage_and_verifies(
    short_root: Path,
    outside_codex_processes: list[subprocess.Popen[bytes]],
    operator_pane_environment: dict[str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The whole arc against a real herdr instance, a real daemon and a stub Codex.

    Eight acceptance facts share this one run -- see the module docstring for why
    they are not eight tests.

    The run happens with `_OUTSIDE_CODEX_PROCESSES` unrelated `codex`-named processes
    live on the host, in their own Codex world outside this run's scratch root, AND
    with this process carrying the release host operator shell's own herdr pane
    environment (`operator_pane_environment`). Both are the release host's condition,
    and the second is the one that actually broke the run.
    """
    run = _run_controller(root=short_root, never_idle=False, timeout=PASSING_RUN_TIMEOUT)
    records = run.records()
    diagnostic = (
        f"exit={run.completed.returncode}\n"
        f"stdout:\n{run.completed.stdout}\nstderr:\n{run.completed.stderr}"
    )

    # 1. Exactly one `passed` record per required stage, in order.
    assert [record["stage"] for record in records] == list(
        REQUIRED_STAGES
    ), f"the controller did not record each required stage exactly once, in order\n{diagnostic}"
    assert [record["status"] for record in records] == ["passed"] * len(
        REQUIRED_STAGES
    ), f"not every recorded stage passed\n{diagnostic}"
    assert run.completed.returncode == 0, f"the controller exited non-zero\n{diagnostic}"

    # 2. The CHECKED-IN verifier grades that evidence directory as passed. The
    #    controller's own verdict is not evidence about the verifier's.
    verdict = _checked_in_verifier()(argv=[str(run.evidence / "lifecycle.jsonl")])
    assert verdict == 0, (
        "the shipped verifier refused the evidence: " f"{capsys.readouterr().err}\n{diagnostic}"
    )

    # 3. The replacement record names BOTH rollout ids, and they DIFFER. A
    #    replacement that reported one id, or the same id twice, would be the
    #    resume-reattach defect `overseer/AGENTS.md` records -- a restart that
    #    consumed a declaration and handed back the same exhausted window.
    replacement = next(record for record in records if record["stage"] == "replacement")
    rollouts = _rollout_ids(text=replacement["detail"])
    assert (
        len(rollouts) >= 2
    ), f"the replacement detail names fewer than two rollout ids: {replacement['detail']!r}"
    predecessor, successor = rollouts[0], rollouts[1]
    assert predecessor != successor, (
        "the replacement detail names the SAME rollout as predecessor and successor, so no "
        f"window was actually reset: {replacement['detail']!r}"
    )

    # 4. Every herdr command the controller issued named the exercise instance.
    #    Observed from the shim's log, not grepped out of the script.
    commands = run.herdr_commands()
    assert commands, "the shim logged no herdr commands at all, so this proves nothing"
    instance = _instance_of(run=run)
    unscoped = [command for command in commands if f"--session {instance}" not in command]
    assert not unscoped, (
        "these herdr commands did not name the exercise instance, so they addressed the "
        f"operator's default server: {unscoped}"
    )

    # 5. The daemon's OWN snapshot bound the topic to the stub's own rollout, inside
    #    the controller's adoption window. The bootstrap record names the rollout the
    #    stub came up on, and the adoption record is the daemon's answer about it; that
    #    pairing is the fact, and asserting only "adoption passed" would not state it.
    bootstrap = next(record for record in records if record["stage"] == "bootstrap")
    adoption = next(record for record in records if record["stage"] == "adoption")
    predecessor_id = _rollout_ids(text=bootstrap["detail"])[0]
    assert f"codex:{predecessor_id}" in adoption["detail"], (
        "the daemon's snapshot did not bind the topic to the rollout the stub came up "
        f"on: bootstrap={bootstrap['detail']!r} adoption={adoption['detail']!r}"
    )

    # 6. The decoys outlived the run, so fact 1 was reached WITH the host condition
    #    present rather than after it quietly went away.
    assert (
        len(_codex_named_pids(processes=outside_codex_processes)) == _OUTSIDE_CODEX_PROCESSES
    ), "the unrelated `codex` processes did not survive the run, so it proves nothing"

    # 7. The daemon's own snapshot row for the topic names a pane INSIDE the exercise
    #    instance. This is the fact the operator shell's inherited pane environment
    #    destroyed: the controller drove a stray startup pane rooted outside the
    #    watched repo, nothing adopted the track, and the row carried `tmux: null`
    #    with `restart_model.reason: pane-absent` -- while the failure was reported
    #    one stage later as a Codex-identity problem.
    _assert_pane_inside_the_exercise_instance(run=run, diagnostic=diagnostic)

    # 8. Neither the exercise server nor the shell in its pane inherited one of this
    #    process's terminal-owner values.
    _assert_nothing_inherited_the_pane_environment(run=run, decoys=operator_pane_environment)


def _assert_pane_inside_the_exercise_instance(*, run: ExerciseRun, diagnostic: str) -> None:
    """The daemon bound the track to the exercise instance's own pane, not a null pane."""
    row = run.snapshot_row(topic=TOPIC)
    coordinate = row.get("tmux")
    assert isinstance(coordinate, str) and coordinate, (
        "the exercise daemon's snapshot row for the topic carries no pane at all, so the "
        f"daemon never located the exercise herdr pane\nrow={row}\n{diagnostic}"
    )
    decoded = herdr_identity.decode_target(value=coordinate)
    herdr_target = decoded.herdr
    assert herdr_target is not None, (
        f"the snapshot row's pane coordinate is not a herdr target: {coordinate!r} "
        f"({decoded.error})"
    )
    assert herdr_target.socket_path == run.socket_path, (
        "the snapshot row names a pane on a DIFFERENT herdr instance: "
        f"{herdr_target.socket_path!r} is not the exercise's {run.socket_path!r}"
    )
    assert herdr_target.pane_id == AGENT_PANE, (
        f"the snapshot row names pane {herdr_target.pane_id!r} rather than the pane the "
        f"controller drives ({AGENT_PANE}), so the exercise and the daemon disagree "
        "about which pane the track lives in"
    )


def _assert_nothing_inherited_the_pane_environment(
    *, run: ExerciseRun, decoys: Mapping[str, str]
) -> None:
    """Read from each process's OWN `/proc` environment, never from the assembled dict.

    A scrub asserted against its own input would prove the function was called. The
    exercise's own `HERDR_SOCKET_PATH` is deliberately not exempted here: the run
    OVERWRITES it with the socket of the server it started, so a decoy value
    surviving in a child is a leak by the same test as every other name.
    """
    assert run.server_environ, "the exercise herdr server's environment could not be read"
    assert run.pane_shell_environ, "the exercise pane shell's environment could not be read"
    for label, observed in (
        ("herdr server", run.server_environ),
        (f"shell in pane {AGENT_PANE}", run.pane_shell_environ),
    ):
        inherited = _inherited_decoys(observed=observed, decoys=decoys)
        assert not inherited, (
            f"the exercise {label} inherited this process's terminal-owner environment "
            f"instead of being scoped to the exercise instance: {inherited}"
        )


@pytest.mark.integration
def test_a_codex_that_never_goes_idle_fails_its_first_stage_and_stops(short_root: Path) -> None:
    """A stub that never becomes idle must stop the run where it stalls.

    The honest shape of an unfinished exercise: a `failed` record for the stage
    that could not complete, NOTHING recorded after it, and a non-zero exit. A
    controller that skipped ahead would leave evidence claiming observations it
    never made.
    """
    run = _run_controller(root=short_root, never_idle=True, timeout=NEVER_IDLE_RUN_TIMEOUT)
    records = run.records()
    diagnostic = (
        f"exit={run.completed.returncode}\n"
        f"stdout:\n{run.completed.stdout}\nstderr:\n{run.completed.stderr}"
    )

    assert records, f"the controller recorded nothing at all\n{diagnostic}"
    failed = [index for index, record in enumerate(records) if record["status"] == "failed"]
    assert failed == [
        len(records) - 1
    ], f"expected exactly one failed record, as the LAST record: {records}\n{diagnostic}"
    assert records[-1]["stage"] == REQUIRED_STAGES[0], (
        "a Codex that never goes idle cannot complete the FIRST stage, so that is the stage "
        f"the failure belongs to: {records[-1]}"
    )
    assert records[-1]["detail"], "a failed record must say what could not be observed"
    assert run.completed.returncode != 0, f"the controller exited zero after failing\n{diagnostic}"

    # The same evidence must be refused by the shipped verifier.
    verdict = _checked_in_verifier()(argv=[str(run.evidence / "lifecycle.jsonl")])
    assert verdict != 0, "the shipped verifier accepted a failed lifecycle"


def _host_home(*, root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for the operator's HOME, carrying an already-provisioned prefix.

    The isolation tests must never be able to touch the REAL
    `~/.local/share/livespec-overseer` -- including while they are red -- so HOME is
    redirected and the prefix the exercise must not reach is created here instead.
    `~/.cache` is linked through to the real one for the same reason `_scratch_home`
    links it: a cold `uv` cache rebuilds the whole environment.
    """
    cache = Path.home() / ".cache"
    host = root / "host-home"
    (host / _RUNTIME_PREFIX_RELATIVE).mkdir(parents=True)
    (host / ".cache").symlink_to(cache)
    monkeypatch.setenv("HOME", str(host))
    return host


def _daemon_executable(*, home: Path) -> Path:
    """Where the shipped `overseer-start` looks for this version's daemon under `home`."""
    return runtime_prefix.daemon_executable(prefix=runtime_prefix.runtime_prefix(home=home))


def _interpreter_of(*, executable: Path) -> str:
    """The interpreter path a console script execs, whichever shebang form it got.

    A prefix under a short root gets the ordinary `#!<python>` shebang -- the form
    the defect was measured in, and the form the exercise's own `ovx-` root always
    produces. A prefix whose absolute path overruns the kernel's shebang bound gets
    the portable `#!/bin/sh` wrapper instead, which execs the same interpreter from
    its SECOND line; reading only the first line there would report `/bin/sh` and
    make a poisoned runtime look clean.
    """
    lines = executable.read_text(encoding="utf-8").splitlines()
    first = lines[0].removeprefix("#!").strip()
    if Path(first).name not in _PORTABLE_SHEBANG_SHELLS:
        return first
    wrapped = _PORTABLE_SHEBANG_EXEC.match(lines[1])
    assert wrapped is not None, f"unrecognized shebang wrapper in {executable}: {lines[:2]}"
    return wrapped.group(1)


def _rollout_ids(*, text: str) -> list[str]:
    """Every canonical Codex rollout uuid named in `text`, in order of appearance."""
    pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    return pattern.findall(text)


def _instance_of(*, run: ExerciseRun) -> str:
    """The exercise instance name, read back from the commands that were issued."""
    for command in run.herdr_commands():
        parts = command.split()
        if "--session" in parts:
            return parts[parts.index("--session") + 1]
    raise AssertionError("no logged herdr command carried --session at all")
