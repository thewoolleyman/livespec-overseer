"""The Codex-on-Herdr lifecycle controller, driven against a REAL herdr instance.

This is the in-sandbox half of `overseer-uzvcbn.4`. The host-captured half -- the
same controller against an AUTHENTICATED Codex under
`scripts/overseer-live-exercise.sh` -- is a release-host obligation and is NOT
discharged here; what these exercises prove is that the controller drives the
shipped mechanics correctly when the only thing stubbed is the agent binary.

**Everything except Codex is real.** A genuine `herdr --session <unique> server`,
a genuine pane, the released `overseerd` the shipped `overseer-start` provisions
and launches, the real mapping store, the real injection-stamp sidecar and the
real `/proc`-backed Codex discovery join. The agent is `tests/stub_codex.py`,
which implements only the surfaces the shipped code reads -- `comm`, a held
rollout fd, a `session_index.jsonl` record on `/rename`, and a pane frame
`signals.py` parses. Nothing in the daemon is patched, seamed or faked.

**The expensive run happens ONCE, inside one test, deliberately.** The full arc
takes minutes, and this suite runs under `pytest -n <workers>` with the default
per-test distribution, so a module-scoped fixture would be re-entered by every
worker that drew a test from this file -- paying the whole arc two or three times
over. The four acceptance facts that share a run are therefore asserted together,
each with its own message, rather than split into four tests that would each pay
for their own daemon.

**Session isolation is herdr's own `--session` mechanism**, and the exercise
additionally runs under a scratch `HOME`, so the mapping store, the stamp sidecar,
the watch declaration and the Codex index are all disposable. The operator's own
daemon, store and sessions are never addressed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from herdr_live_server import require_herdr, start_server, stop_server, unique_session

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


@pytest.fixture
def short_root() -> Iterator[Path]:
    """A disposable root short enough for a herdr socket address to fit under it."""
    root = Path(tempfile.mkdtemp(prefix=_SHORT_ROOT_PREFIX))
    try:
        yield root
    finally:
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
    """A disposable HOME that can still reach the warm caches.

    `~/.cache` is symlinked because `uv` keys its cache off HOME and a cold one
    rebuilds the whole environment -- documented in `overseer/AGENTS.md` as looking
    exactly like a daemon hang. `~/.local/share/livespec-overseer` is symlinked so
    `overseer-start` reuses an already-provisioned daemon runtime prefix instead of
    reinstalling the release from git for every exercise.
    """
    home = root / "home"
    (home / ".local" / "share").mkdir(parents=True)
    for shared in (Path.home() / ".cache", Path.home() / ".local" / "share" / "livespec-overseer"):
        link = home / shared.relative_to(Path.home())
        link.parent.mkdir(parents=True, exist_ok=True)
        if shared.exists():
            link.symlink_to(shared)
    return home


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


def _run_controller(*, root: Path, never_idle: bool, timeout: float) -> ExerciseRun:
    """Start one exercise herdr instance and drive the controller against it."""
    require_herdr()
    home = _scratch_home(root=root)
    binaries, herdr_log = _exercise_bin(root=root, never_idle=never_idle)
    evidence = root / "evidence"
    evidence.mkdir()

    # The server runs under the scratch HOME so its socket, its session registry
    # and everything the controller writes share one disposable root.
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["PATH"] = f"{binaries}{os.pathsep}{environment['PATH']}"
    session = unique_session(label=_SESSION_LABEL)
    previous_home = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        server = start_server(scratch=root / "server", session=session, env=environment)
        environment["HERDR_SOCKET_PATH"] = server.socket_path
        environment.update(
            {
                "OVERSEER_EXERCISE_BACKEND": "herdr",
                "OVERSEER_EXERCISE_INSTANCE": session,
                "OVERSEER_EXERCISE_TOPIC": TOPIC,
                "OVERSEER_EXERCISE_EVIDENCE": str(evidence),
                "OVERSEER_EXERCISE_REPO": str(root / "repo"),
                "CODEX_HOME": str(home / ".codex"),
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
        finally:
            stop_server(session=session)
    finally:
        if previous_home is None:  # pragma: no cover - HOME is always set on this host
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = previous_home
    return ExerciseRun(completed=completed, evidence=evidence, herdr_log=herdr_log)


def test_the_controller_is_a_checked_in_executable() -> None:
    """The exercise coordinator runs this by path, so the bit is part of shipping it."""
    assert CONTROLLER.is_file(), f"the controller is missing from the repository: {CONTROLLER}"
    assert os.access(CONTROLLER, os.X_OK), f"the controller is not executable: {CONTROLLER}"


@pytest.mark.integration
def test_a_stub_codex_run_records_every_lifecycle_stage_and_verifies(
    short_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole arc against a real herdr instance, a real daemon and a stub Codex.

    Four acceptance facts share this one run -- see the module docstring for why
    they are not four tests.
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
