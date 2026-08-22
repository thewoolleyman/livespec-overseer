"""Gates for the LLM half of the shipped foreman product.

The foreman runtime is split: deterministic Python computes fields such as
``exit_reason``, while the model consumes ``prose/foreman.md`` to decide what to
do with those fields. These tests keep the two halves connected.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from foreman_act_types import ACTION_IDS

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / ".claude-plugin"
PROSE = PLUGIN_ROOT / "prose" / "foreman.md"
RUNTIME = PLUGIN_ROOT / "bin" / "foreman-runtime"


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    assert "PYTHONPATH" not in env
    return env


def _tmux(*, socket: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["tmux", "-S", str(socket), *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )


def _pane_pid(*, socket: Path, session: str) -> str:
    completed = _tmux(
        socket=socket,
        args=["display-message", "-p", "-t", session, "#{pane_pid}"],
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def _snapshot(*, repo: Path, tick_generation: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "daemon_instance_id": "daemon-contract",
        "tick_generation": tick_generation,
        "written_at": "2026-08-06T10:00:00Z",
        "needs_attention": {
            "schema_version": 1,
            "generated_at": "2026-08-06T10:00:00Z",
            "items": [],
        },
        "rows": [
            {
                "repo": str(repo),
                "topic": "alpha",
                "tmux": "alpha",
                "runtime": "codex",
                "status": "session-gone",
                "session_identity": f"none:{repo}:alpha",
            }
        ],
    }


def _register_foreman_session(*, repo: Path, home: Path, socket: Path) -> None:
    created = _tmux(
        socket=socket,
        args=["new-session", "-d", "-s", "repo-foreman", "-c", str(repo), "sleep 60"],
    )
    assert created.returncode == 0, created.stderr
    pane_pid = _pane_pid(socket=socket, session="repo-foreman")
    proc_start = (Path("/proc") / pane_pid / "stat").read_text(encoding="utf-8").split()[21]
    sessions_dir = home / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / f"{pane_pid}.json").write_text(
        json.dumps(
            {
                "pid": int(pane_pid),
                "name": "repo-foreman",
                "cwd": str(repo),
                "status": "idle",
                "procStart": proc_start,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _run_runtime(
    *, repo: Path, home: Path, socket: Path, snapshot: dict[str, object], now: float
) -> dict[str, object]:
    snapshot_path = home / "runtime-status.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    env = {
        **_scrubbed_env(),
        "HOME": str(home),
        "TMUX": f"{socket},0,0",
    }
    completed = subprocess.run(  # noqa: S603
        [
            str(RUNTIME),
            "--repo",
            str(repo),
            "--watch-set-path",
            str(home / ".livespec-overseer-repos.json"),
            "--snapshot-path",
            str(snapshot_path),
            "--now-epoch",
            str(now),
        ],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return parsed


def _missing_action_ids(*, text: str) -> list[str]:
    return [action_id for action_id in ACTION_IDS if action_id not in text]


CANONICAL_ESCALATION_PATH = "tmp/overseer/foreman/escalations/<repo-slug>-foreman.json"
AMBIGUOUS_ESCALATION_PATH = "escalations/<topic>.json"


def _escalation_filename_errors(*, text: str) -> list[str]:
    """Both defects that make a foreman escalation land somewhere unread.

    `_supervisor_foreman_escalation` resolves the file by the foreman track's topic,
    and `foreman_runtime_identity.canonical_session_name` makes that topic
    `<repo-slug>-foreman`. So that filename is the ONLY one the daemon reads. A
    contract that names `<topic>.json` invites a plan-topic name or a bare
    `foreman.json`, either of which is written and never surfaced — a silent loss,
    strictly worse than the blocking picker this path replaces.
    """
    errors: list[str] = []
    if CANONICAL_ESCALATION_PATH not in text:
        errors.append("canonical-escalation-path-absent")
    if AMBIGUOUS_ESCALATION_PATH in text:
        errors.append("ambiguous-escalation-path-present")
    return errors


def _exit_contract_errors(*, text: str) -> list[str]:
    required = (
        "/loop",
        "hourly",
        "foreman-runtime",
        "exit_reason",
        "converged",
        "hard-tick-budget",
        "tmp/overseer/foreman/escalations/<repo-slug>-foreman.json",
        "foreman-escalated",
        "resume the loop",
        "token-free watcher remains armed",
        "O14/C5/O13/C6",
    )
    return [term for term in required if term not in text]


def test_all_shipped_action_ids_are_discoverable_from_the_contract() -> None:
    text = PROSE.read_text(encoding="utf-8")

    assert _missing_action_ids(text=text) == []
    sabotaged = text.replace("human_valve", "")
    assert _missing_action_ids(text=sabotaged) == ["human_valve"]


def test_runtime_exit_reason_is_carried_to_the_resume_question_contract(*, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "alpha").mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    socket = tmp_path / "tmux.sock"
    (home / ".livespec-overseer-repos.json").write_text(
        json.dumps({"repos": [str(repo)]}) + "\n", encoding="utf-8"
    )
    _register_foreman_session(repo=repo, home=home, socket=socket)
    try:
        first = _run_runtime(
            repo=repo,
            home=home,
            socket=socket,
            snapshot=_snapshot(repo=repo, tick_generation=1),
            now=1000.0,
        )
        assert first["exit_reason"] is None
        assert (
            _run_runtime(
                repo=repo,
                home=home,
                socket=socket,
                snapshot=_snapshot(repo=repo, tick_generation=1),
                now=1001.0,
            )["exit_reason"]
            is None
        )
        changed = _snapshot(repo=repo, tick_generation=2)
        assert (
            _run_runtime(repo=repo, home=home, socket=socket, snapshot=changed, now=4600.0)[
                "exit_reason"
            ]
            == "converged"
        )
        assert (
            _run_runtime(repo=repo, home=home, socket=socket, snapshot=changed, now=8200.0)[
                "exit_reason"
            ]
            == "converged"
        )
    finally:
        _tmux(socket=socket, args=["kill-server"])

    text = PROSE.read_text(encoding="utf-8")
    assert _exit_contract_errors(text=text) == []
    sabotaged = text.replace("foreman-escalated", "")
    assert _exit_contract_errors(text=sabotaged) == ["foreman-escalated"]


def test_the_contract_names_only_the_escalation_filename_the_daemon_reads() -> None:
    text = PROSE.read_text(encoding="utf-8")

    assert _escalation_filename_errors(text=text) == []

    # Discriminating control: the check must FAIL on each defect it exists to catch,
    # or it is a check that cannot fail and proves nothing about the contract.
    assert _escalation_filename_errors(text=text.replace(CANONICAL_ESCALATION_PATH, "")) == [
        "canonical-escalation-path-absent"
    ]
    assert _escalation_filename_errors(text=text + AMBIGUOUS_ESCALATION_PATH) == [
        "ambiguous-escalation-path-present"
    ]
