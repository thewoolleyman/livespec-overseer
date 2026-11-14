"""Contract checks for the Claude-on-tmux isolated-exercise controller."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from overseer import runtime_prefix
from overseer.tmuxio import new_session_args

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROLLER = REPO_ROOT / "scripts" / "overseer-live-exercise-claude-tmux.sh"
STUB = REPO_ROOT / "tests" / "stub_claude.py"
STUB_SHIM_PREPARER = REPO_ROOT / "scripts" / "overseer-live-exercise-stub-shims.sh"
VERIFIER = REPO_ROOT / "scripts" / "overseer_live_exercise_evidence.py"


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
            "OVERSEER_EXERCISE_CLAUDE_READY_TIMEOUT": "4",
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
