"""Contract checks for the Claude-on-tmux isolated-exercise controller."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket as socket_module
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest

from overseer import runtime_prefix
from overseer.tmuxio import new_session_args

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROLLER = REPO_ROOT / "scripts" / "overseer-live-exercise-claude-tmux.sh"
STUB = REPO_ROOT / "tests" / "stub_claude.py"
STUB_SHIM_PREPARER = REPO_ROOT / "scripts" / "overseer-live-exercise-stub-shims.sh"
VERIFIER = REPO_ROOT / "scripts" / "overseer_live_exercise_evidence.py"

# A failed fixture run copies what it observed here, and check-per-file-coverage
# uploads this one repo-relative path as a workflow artifact when the job fails, so
# a timeout on a loaded runner leaves the daemon's side of the story behind.
FAILURE_EVIDENCE_ROOT = REPO_ROOT / "tmp" / "exercise-failure-evidence"


def _retain_failure_evidence(*, sources: Sequence[Path], destination: Path) -> None:
    """Copy each source's regular files under `destination/<source name>`.

    A socket, an absent path, or anything else that is not a regular file is
    skipped: the copy must never be the thing that fails.
    """
    for source in sources:
        if source.is_dir():
            files = [path for path in source.rglob("*") if path.is_file()]
            for path in files:
                target = destination / source.name / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(path, target)
        elif source.is_file():
            destination.mkdir(parents=True, exist_ok=True)
            _ = shutil.copy2(source, destination / source.name)


def _provision_daemon_runtime(*, home: Path) -> None:
    """Give the isolated HOME the installed daemon `overseer-start` requires."""
    daemon = runtime_prefix.ensure_runtime(
        prefix=runtime_prefix.runtime_prefix(home=home),
        install_source=str(REPO_ROOT),
    )
    assert daemon is not None, f"could not provision isolated daemon runtime at {home}"


def test_controller_is_checked_in_executable_and_uses_only_the_exercise_socket() -> None:
    """The controller is executable and centralizes tmux behind the private socket."""
    assert CONTROLLER.is_file(), "the Claude tmux controller is missing"
    assert os.access(CONTROLLER, os.X_OK), "the Claude tmux controller is not executable"
    source = CONTROLLER.read_text(encoding="utf-8")
    assert 'tmux -S "$endpoint"' in source
    assert "tmux " not in source.replace('tmux -S "$endpoint"', "")


def test_replacement_evidence_labels_both_process_identity_components() -> None:
    """A reviewer can read the predecessor and successor PID/start-time pairs."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "predecessor pid=" in source
    assert "successor pid=" in source
    assert "starttime=" in source


def test_controller_gives_a_stub_the_same_bootstrap_ancestry_and_scopes_successor() -> None:
    """The released bootstrap sees Claude ancestry and the daemon verifies replacement."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "CLAUDECODE=1" in source
    assert '"$(snapshot_row session_identity)" == "$successor"' in source


def test_controller_keeps_a_stable_pane_and_private_server_path_for_replacement() -> None:
    """Window renames and a late-added stub PATH cannot break the shipped relaunch."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "agent_target=\"$(tx new-window -d -P -F '#{pane_id}'" in source
    assert 'tx set-environment -g PATH "$PATH"' in source
    assert "tx set-environment -gu PYTHONHOME" in source
    assert "env -u PYTHONHOME" in source


def test_checked_in_claude_stub_and_launcher_are_available_for_the_private_tmux_run() -> None:
    """The proof uses tracked fixtures instead of writing an agent double under `/tmp`."""
    assert STUB.is_file(), "the idle-Claude fixture is missing"
    preparer = STUB_SHIM_PREPARER.read_text(encoding="utf-8")
    assert "--claude-script" in preparer
    assert '"$bin_dir/claude"' in preparer


def _drive_controller_through_every_stage(
    *, socket: Path, environment: dict[str, str], evidence: Path
) -> None:
    """Run the controller on the private server and check its six-stage evidence."""
    try:
        completed = subprocess.run(
            [str(CONTROLLER)],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            env=environment,
        )
    finally:
        _ = subprocess.run(
            ["tmux", "-S", str(socket), "kill-server"],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
    assert completed.returncode == 0, completed.stderr
    records = [json.loads(line) for line in (evidence / "lifecycle.jsonl").read_text().splitlines()]
    assert [(record["stage"], record["status"]) for record in records] == [
        ("bootstrap", "passed"),
        ("adoption", "passed"),
        ("wrap-up", "passed"),
        ("declaration", "passed"),
        ("replacement", "passed"),
        ("continuation", "passed"),
    ]
    replacement = records[4]["detail"]
    assert "predecessor pid=" in replacement and "successor pid=" in replacement
    assert "starttime=" in replacement
    verified = subprocess.run(
        [sys.executable, str(VERIFIER), str(evidence / "lifecycle.jsonl")],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in environment.items() if key != "PYTHONHOME"},
    )
    assert verified.returncode == 0, verified.stderr


def test_controller_drives_the_committed_idle_claude_stub_on_a_private_tmux_server(
    tmp_path: Path,
) -> None:
    """The complete fixture run proves the six-stage evidence contract end to end."""
    if shutil.which("tmux") is None:
        pytest.skip("tmux is unavailable")
    home = tmp_path / "home"
    home.mkdir()
    _provision_daemon_runtime(home=home)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    binaries = tmp_path / "bin"
    prepared = subprocess.run(
        [
            str(STUB_SHIM_PREPARER),
            "--bin-dir",
            str(binaries),
            "--claude-script",
            str(STUB),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    socket = tmp_path / "tmux.sock"
    instance = f"claude-exercise-{uuid.uuid4().hex}"
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }
    environment.update(
        {
            "HOME": str(home),
            "PATH": f"{binaries}{os.pathsep}{environment['PATH']}",
            "PYTHONHOME": "/invalid-python-home",
            "OVERSEER_EXERCISE_BACKEND": "tmux",
            "OVERSEER_EXERCISE_INSTANCE": instance,
            "OVERSEER_EXERCISE_ENDPOINT": str(socket),
            "OVERSEER_EXERCISE_TOPIC": "stub-claude-topic",
            "OVERSEER_EXERCISE_EVIDENCE": str(evidence),
            # Long enough that the resume line wraps past the retained pane's few rows.
            "OVERSEER_EXERCISE_REPO": str(
                tmp_path / ("a-long-scratch-directory-name-" * 3) / "repo"
            ),
        }
    )
    started = subprocess.run(
        ["tmux", "-S", str(socket), *new_session_args(args=["-d", "-s", instance])],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert started.returncode == 0, started.stderr
    try:
        _drive_controller_through_every_stage(
            socket=socket, environment=environment, evidence=evidence
        )
    except (AssertionError, subprocess.TimeoutExpired):
        _retain_failure_evidence(
            sources=(
                evidence,
                Path(environment["OVERSEER_EXERCISE_REPO"]) / "tmp",
                home / ".livespec-overseer-status.json",
                home / ".livespec-overseer.jsonl",
                home / ".livespec-overseer-repos.json",
            ),
            destination=FAILURE_EVIDENCE_ROOT / instance,
        )
        raise


def test_controller_records_the_first_unfinishable_stage_when_claude_never_idles(
    tmp_path: Path,
) -> None:
    """A Claude that never idles fails `bootstrap`, appends no later stage, exits non-zero."""
    if shutil.which("tmux") is None:
        pytest.skip("tmux is unavailable")
    home = tmp_path / "home"
    home.mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    binaries = tmp_path / "bin"
    prepared = subprocess.run(
        [
            str(STUB_SHIM_PREPARER),
            "--bin-dir",
            str(binaries),
            "--claude-script",
            str(STUB),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    socket = tmp_path / "tmux.sock"
    instance = f"claude-exercise-{uuid.uuid4().hex}"
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != "COVERAGE_PROCESS_START" and not key.startswith("COV_CORE_")
    }
    environment.update(
        {
            "HOME": str(home),
            "PATH": f"{binaries}{os.pathsep}{environment['PATH']}",
            "STUB_CLAUDE_NEVER_IDLE": "1",
            "OVERSEER_EXERCISE_CLAUDE_IDLE_TIMEOUT": "4",
            "OVERSEER_EXERCISE_BACKEND": "tmux",
            "OVERSEER_EXERCISE_INSTANCE": instance,
            "OVERSEER_EXERCISE_ENDPOINT": str(socket),
            "OVERSEER_EXERCISE_TOPIC": "stub-claude-topic",
            "OVERSEER_EXERCISE_EVIDENCE": str(evidence),
            "OVERSEER_EXERCISE_REPO": str(tmp_path / "repo"),
        }
    )
    started = subprocess.run(
        ["tmux", "-S", str(socket), *new_session_args(args=["-d", "-s", instance])],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert started.returncode == 0, started.stderr
    try:
        completed = subprocess.run(
            [str(CONTROLLER)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=environment,
        )
    finally:
        _ = subprocess.run(
            ["tmux", "-S", str(socket), "kill-server"],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
    assert completed.returncode != 0
    records = [json.loads(line) for line in (evidence / "lifecycle.jsonl").read_text().splitlines()]
    assert [(record["stage"], record["status"]) for record in records] == [("bootstrap", "failed")]


def test_trust_gate_writes_claude_profile_shape_not_codex_settings(tmp_path: Path) -> None:
    """Folder trust and onboarding land in `.claude.json` as real Claude Code reads them."""
    source = CONTROLLER.read_text(encoding="utf-8")
    start = source.index("clear_claude_trust_gate() {")
    function = source[start : source.index("\n}\n", start) + 3]
    home = tmp_path / "home"
    home.mkdir()
    profile = home / ".claude.json"
    profile.write_text(json.dumps({"userID": "keep", "projects": {"/other": {"x": 1}}}))
    repo = "/scratch/repo"
    script = f'claude_home="$HOME/.claude"\nrepo={repo}\n{function}\nclear_claude_trust_gate\n'
    env = {**os.environ, "HOME": str(home)}
    env.pop("CLAUDE_CONFIG_DIR", None)
    subprocess.run(["bash", "-c", script], env=env, check=True)
    value = json.loads(profile.read_text(encoding="utf-8"))
    assert value["hasCompletedOnboarding"] is True
    assert value["projects"][repo]["hasTrustDialogAccepted"] is True
    assert value["userID"] == "keep"
    assert value["projects"]["/other"] == {"x": 1}
    assert not (home / ".claude" / "settings.json").exists()


def _controller_functions(*names: str) -> str:
    """Return the named controller functions verbatim, so a test runs the shipped bodies."""
    source = CONTROLLER.read_text(encoding="utf-8")
    bodies = []
    for name in names:
        start = source.index(f"\n{name}() {{\n") + 1
        bodies.append(source[start : source.index("\n}\n", start) + 3])
    return "".join(bodies)


def _observe(*, state_file: Path, since: float) -> subprocess.CompletedProcess[str]:
    script = (
        f"state_file={state_file}\ndeclaration_since={since}\n"
        + _controller_functions("observe_declaration")
        + "observe_declaration\n"
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


def test_idle_input_and_declaration_waits_have_separate_bounds() -> None:
    """The bootstrap idle wait and the declaration wait no longer share one bound."""
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "CLAUDE_READY_TIMEOUT" not in source
    assert 'wait_until "$CLAUDE_IDLE_TIMEOUT" claude_pane_is_idle' in source
    assert 'wait_until "$DECLARATION_TIMEOUT" declaration_is_observed' in source


def test_a_fresh_ready_line_is_observed_as_declared(tmp_path: Path) -> None:
    """A `ready` written after the submit is this declaration."""
    state_file = tmp_path / ".overseer-state"
    state_file.write_text("ready\n", encoding="utf-8")
    observed = _observe(state_file=state_file, since=state_file.stat().st_mtime - 5)
    assert observed.returncode == 0
    assert observed.stdout.startswith("declared\t")


def test_a_declaration_the_daemon_already_consumed_is_observed(tmp_path: Path) -> None:
    """The restart overwrites `ready` with `restarted:`; that still proves the declaration."""
    state_file = tmp_path / ".overseer-state"
    state_file.write_text(
        "restarted: restart completed; consumed ready declaration\n", encoding="utf-8"
    )
    observed = _observe(state_file=state_file, since=state_file.stat().st_mtime - 5)
    assert observed.returncode == 0
    assert observed.stdout.startswith("consumed\t")


def test_a_state_written_before_the_submit_is_never_this_declaration(tmp_path: Path) -> None:
    """A `ready` left by an earlier run in a reused scratch repository does not count."""
    state_file = tmp_path / ".overseer-state"
    state_file.write_text("ready\n", encoding="utf-8")
    observed = _observe(state_file=state_file, since=state_file.stat().st_mtime + 60)
    assert observed.returncode == 1
    assert observed.stdout.startswith("pending\tstale 'ready'")


def test_an_absent_or_unrelated_state_is_still_pending(tmp_path: Path) -> None:
    """No file, or a value other than the declaration, keeps the stage waiting."""
    state_file = tmp_path / ".overseer-state"
    absent = _observe(state_file=state_file, since=0)
    assert (absent.returncode, absent.stdout) == (1, "pending\tabsent\n")
    state_file.write_text("winding-down\n", encoding="utf-8")
    other = _observe(state_file=state_file, since=0)
    assert (other.returncode, other.stdout) == (1, "pending\t'winding-down'\n")


def _run_declaration_stage(*, tmp_path: Path, on_submit: str) -> subprocess.CompletedProcess[str]:
    """Run the shipped declaration stage against stand-in pane and lifecycle helpers."""
    state_file = tmp_path / "tmp" / "overseer" / "topic" / ".overseer-state"
    state_file.parent.mkdir(parents=True)
    script = "\n".join(
        (
            f"state_file={state_file}",
            f"repo={tmp_path}",
            f"package={tmp_path}",
            "agent_target=%1",
            "POLL_SECONDS=1",
            "WRAPUP_TIMEOUT=2",
            "DECLARATION_TIMEOUT=3",
            "claude_pane_is_idle() { return 0; }",
            f"pane_submit() {{ {on_submit} return 0; }}",
            'pass_stage() { echo "passed: $2"; }',
            'fail_stage() { echo "failed: $2" >&2; exit 1; }',
            _controller_functions(
                "wait_until", "observe_declaration", "declaration_is_observed", "stage_declaration"
            ),
            "stage_declaration",
        )
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


def test_declaration_consumed_before_the_first_poll_passes_the_stage(tmp_path: Path) -> None:
    """A daemon that restarts the session between two polls no longer fails the stage."""
    completed = _run_declaration_stage(
        tmp_path=tmp_path,
        on_submit=(
            'echo "restarted: restart completed; consumed ready declaration" > "$state_file";'
        ),
    )
    assert completed.returncode == 0, completed.stderr
    assert "already consumed" in completed.stdout


def test_declaration_timeout_names_elapsed_seconds_and_the_last_state(tmp_path: Path) -> None:
    """The failure line says how long it waited and what the state file last held."""
    completed = _run_declaration_stage(
        tmp_path=tmp_path, on_submit='echo winding-down > "$state_file";'
    )
    assert completed.returncode == 1
    assert "s after the declaration was submitted (bound 3s)" in completed.stderr
    assert "last state observed" in completed.stderr
    assert "'winding-down'" in completed.stderr


def _run_stage(
    *, tmp_path: Path, rows: list[dict[str, object]], functions: tuple[str, ...], preamble: str
) -> subprocess.CompletedProcess[str]:
    """Run one shipped snapshot-polling stage against a fixed status snapshot."""
    snapshot = tmp_path / ".livespec-overseer-status.json"
    _ = snapshot.write_text(json.dumps({"rows": rows}), encoding="utf-8")
    script = "\n".join(
        (
            f"snapshot={snapshot}",
            "topic=stub-topic",
            f"repo={tmp_path}",
            "agent_target=%1",
            "OVERSEER_EXERCISE_EPIC=stub-epic",
            "POLL_SECONDS=1",
            'shipped() { python3 "$@"; }',
            'pass_stage() { echo "passed: $2"; }',
            'fail_stage() { echo "$1 FAILED — $2" >&2; exit 1; }',
            _controller_functions(*functions),
            preamble,
        )
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


def test_wrapup_timeout_names_elapsed_seconds_and_the_rows_last_reading(tmp_path: Path) -> None:
    """A round that never opens reports how long it waited and what the daemon's row said."""
    completed = _run_stage(
        tmp_path=tmp_path,
        rows=[
            {
                "topic": "stub-topic",
                "round_open": False,
                "status": "working",
                "ctx": 75,
                "ctx_source": "pane",
                "ctx_age_seconds": 3,
            }
        ],
        functions=(
            "wait_until",
            "timed_out",
            "snapshot_fields",
            "wrapup_round_is_open",
            "stage_wrapup",
        ),
        preamble="\n".join(
            (
                "WRAPUP_TIMEOUT=2",
                "pane_ctx_remaining() { echo 75; }",
                "overseer_cli() { return 0; }",
                "stage_wrapup",
            )
        ),
    )
    assert completed.returncode == 1
    assert re.search(
        r"wrap-up FAILED — .*after [2-4]s \(bound 2s\), last observed: round_open=False "
        r"status='working' ctx=75 ctx_source='pane' ctx_age_seconds=3",
        completed.stderr,
    ), completed.stderr


def test_wrapup_timeout_says_when_the_daemon_wrote_no_row_for_the_topic(tmp_path: Path) -> None:
    """An absent row is reported as absent, not as a closed round."""
    completed = _run_stage(
        tmp_path=tmp_path,
        rows=[{"topic": "some-other-topic", "round_open": True}],
        functions=(
            "wait_until",
            "timed_out",
            "snapshot_fields",
            "wrapup_round_is_open",
            "stage_wrapup",
        ),
        preamble="\n".join(
            (
                "WRAPUP_TIMEOUT=1",
                "pane_ctx_remaining() { echo 75; }",
                "overseer_cli() { return 0; }",
                "stage_wrapup",
            )
        ),
    )
    assert completed.returncode == 1
    assert "last observed: no snapshot row for 'stub-topic'" in completed.stderr, completed.stderr


def test_adoption_timeout_names_elapsed_seconds_and_the_identity_last_seen(tmp_path: Path) -> None:
    """An adoption that never binds reports the identity and status the row last carried."""
    completed = _run_stage(
        tmp_path=tmp_path,
        rows=[
            {"topic": "stub-topic", "session_identity": "claude:9:9:stub-topic", "status": "idle"}
        ],
        functions=(
            "wait_until",
            "timed_out",
            "snapshot_fields",
            "track_is_adopted",
            "stage_adoption",
        ),
        preamble="\n".join(
            ("ADOPTION_TIMEOUT=1", "predecessor=claude:1:2:stub-topic", "stage_adoption")
        ),
    )
    assert completed.returncode == 1
    assert re.search(
        r"adoption FAILED — .*after [1-3]s \(bound 1s\), last observed: "
        r"session_identity='claude:9:9:stub-topic' status='idle'",
        completed.stderr,
    ), completed.stderr


def test_every_bounded_wait_reports_elapsed_seconds_and_its_last_observation() -> None:
    """Each stage's timeout line goes through `timed_out` with that wait's own bound.

    The declaration wait is the one exception: its line already names the seconds
    since the submit and the state file's last reading, in its own words.
    """
    source = CONTROLLER.read_text(encoding="utf-8")
    bounded_wait = r'wait_until "\$(\w+)" (\w+) \|\| fail_stage [\w-]+ \\\n\s+"([^\n]*)"'
    waits = re.findall(bounded_wait, source)
    assert len(waits) == 7, waits
    for bound, condition, message in waits:
        assert f'$(timed_out "${bound}")' in message, (condition, message)
    assert 'if ! wait_until "$DECLARATION_TIMEOUT" declaration_is_observed; then' in source


def test_failure_evidence_is_retained_under_the_path_ci_uploads(tmp_path: Path) -> None:
    """Regular files are copied under their source's name; sockets and absent paths are skipped."""
    evidence = tmp_path / "evidence"
    (evidence / "nested").mkdir(parents=True)
    _ = (evidence / "lifecycle.jsonl").write_text("{}\n", encoding="utf-8")
    _ = (evidence / "nested" / ".overseer-state").write_text("ready\n", encoding="utf-8")
    snapshot = tmp_path / ".livespec-overseer-status.json"
    _ = snapshot.write_text("{}", encoding="utf-8")
    daemon_dir = tmp_path / "repo-tmp"
    daemon_dir.mkdir()
    _ = (daemon_dir / "daemon.log").write_text("tick\n", encoding="utf-8")
    listener = socket_module.socket(socket_module.AF_UNIX)
    socket_path = Path(tempfile.mkdtemp()) / "s.sock"
    listener.bind(str(socket_path))
    try:
        destination = tmp_path / "retained"
        _retain_failure_evidence(
            sources=(evidence, snapshot, daemon_dir, socket_path, tmp_path / "absent"),
            destination=destination,
        )
    finally:
        listener.close()
        socket_path.unlink()
    retained = sorted(
        str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()
    )
    assert retained == [
        ".livespec-overseer-status.json",
        "evidence/lifecycle.jsonl",
        "evidence/nested/.overseer-state",
        "repo-tmp/daemon.log",
    ]
    assert FAILURE_EVIDENCE_ROOT == REPO_ROOT / "tmp" / "exercise-failure-evidence"


def test_ci_uploads_the_retained_evidence_when_the_coverage_job_fails() -> None:
    """check-per-file-coverage carries an `if: failure()` upload of that one path."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = workflow.index("\n  check-per-file-coverage:\n")
    following = re.search(r"\n  [\w-]+:\n", workflow[start + 1 :])
    job = workflow[start : start + 1 + (following.start() if following else len(workflow))]
    steps = job.split("\n      - name: ")[1:]
    uploads = [step for step in steps if "uses: actions/upload-artifact@v4" in step]
    matching = [step for step in uploads if "path: tmp/exercise-failure-evidence\n" in step]
    assert len(matching) == 1, uploads
    step = matching[0]
    assert "if: ${{ failure() }}" in step
    assert "include-hidden-files: true" in step
    assert "if-no-files-found: ignore" in step
