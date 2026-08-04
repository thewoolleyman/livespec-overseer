"""Executable E2E gate for every shipped plugin ``bin/`` launcher."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import shlex
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_BIN = ROOT / ".claude-plugin" / "bin"
PLUGIN_ROOT = ROOT / ".claude-plugin"


@dataclass(frozen=True, kw_only=True)
class ForemanActContext:
    plugin_root: Path
    repo: Path
    home: Path
    socket: Path
    path: Path


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }
    assert "PYTHONPATH" not in env
    return env


def _write_module(*, path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _materialize_overseer_plugin(*, cache: Path) -> Path:
    plugin_root = cache / "livespec-overseer" / "livespec-overseer" / "test-build"
    shutil.copytree(PLUGIN_ROOT, plugin_root)
    return plugin_root


def _materialize_orchestrator_plugin(*, cache: Path) -> None:
    scripts = (
        cache
        / "livespec-orchestrator-beads-fabro"
        / "livespec-orchestrator-beads-fabro"
        / "test-build"
        / "scripts"
    )
    package = scripts / "livespec_orchestrator_beads_fabro"
    runtime = scripts / "_vendor" / "livespec_runtime" / "work_items"
    _write_module(path=package / "__init__.py", text="")
    _write_module(path=package / "commands" / "__init__.py", text="")
    _write_module(path=scripts / "_vendor" / "livespec_runtime" / "__init__.py", text="")
    _write_module(path=runtime / "__init__.py", text="")
    _write_module(
        path=package / "_ids.py",
        text="""
        def new_work_item_id(*, prefix):
            return f"{prefix}-filed"
        """,
    )
    _write_module(
        path=package / "commands" / "_config.py",
        text="""
        from dataclasses import dataclass


        @dataclass(frozen=True, kw_only=True)
        class StoreConfig:
            prefix: str
            repo_root: object


        def resolve_store_config(*, cwd, work_items_arg):
            _ = work_items_arg
            return StoreConfig(prefix="overseer", repo_root=cwd)
        """,
    )
    _write_module(
        path=package / "types.py",
        text="""
        from dataclasses import dataclass


        @dataclass(frozen=True, kw_only=True)
        class WorkItem:
            id: str
            type: str
            status: str
            title: str
            description: str
            origin: str
            gap_id: object
            rank: str
            assignee: object
            depends_on: object
            captured_at: str
            resolution: object
            reason: object
            audit: object
            superseded_by: object
            spec_commitment_hint: object
            acceptance_criteria: object
            notes: object
        """,
    )
    _write_module(
        path=package / "store.py",
        text="""
        import json


        def append_work_item(*, path, item):
            marker = path.repo_root / "tmp" / "fake-store.jsonl"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"item_id": item.id}) + "\\n", encoding="utf-8")
        """,
    )
    _write_module(
        path=package / "intake_dor.py",
        text="""
        import json
        from dataclasses import dataclass


        @dataclass(frozen=True, kw_only=True)
        class DefinitionOfReadyChecklist:
            single_coherent_done: bool
            autonomously_verifiable: bool
            autonomy_tiered: bool
            dependency_linked: bool
            repo_targeted: bool
            above_floor: bool


        def apply_intake_dor(*, path, item_id, checklist):
            marker = path.repo_root / "tmp" / "fake-intake.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps(
                    {
                        "above_floor": checklist.above_floor,
                        "item_id": item_id,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            return "ready"
        """,
    )
    _write_module(
        path=runtime / "rank.py",
        text="""
        def key_between(*, a, b):
            _ = (a, b)
            return "rank"
        """,
    )


def _status_snapshot(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "daemon_instance_id": "daemon-1",
        "tick_generation": 7,
        "written_at": "2026-08-04T00:00:00Z",
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


def _work_item_file_proposal(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": "work_item_file",
        "repo": str(repo),
        "topic": "alpha",
        "session_name": "alpha",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": f"none:{repo}:alpha",
        },
        "classifier": {"action": "file_work_item"},
        "filing": {
            "target_repo": str(repo),
            "title": "File the delegated fix",
            "description": "Capture this follow-up through intake.",
            "type": "feature",
            "assignee": None,
            "depends_on": [],
            "acceptance_criteria": "Beside tests cover the behavior.",
            "notes": "Filed by foreman-act.",
            "spec_commitment_hint": None,
            "checklist": {
                "single_coherent_done": True,
                "autonomously_verifiable": True,
                "autonomy_tiered": True,
                "dependency_linked": True,
                "repo_targeted": True,
                "above_floor": True,
            },
        },
    }


def _plan_start_proposal(*, repo: Path, topic: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": "plan_start",
        "repo": str(repo),
        "topic": topic,
        "session_name": topic,
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": f"none:{repo}:{topic}",
        },
        "classifier": {
            "action": "start",
            "start": {"repo": str(repo), "topic": topic, "session_name": topic},
        },
    }


def _plan_start_snapshot(*, repo: Path, topic: str) -> dict[str, object]:
    snapshot = _status_snapshot(repo=repo)
    rows = snapshot["rows"]
    assert isinstance(rows, list)
    rows[0] = {
        "repo": str(repo),
        "topic": topic,
        "tmux": topic,
        "runtime": "codex",
        "status": "session-gone",
        "session_identity": f"none:{repo}:{topic}",
    }
    return snapshot


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


def _registry_topics(*, store: Path) -> set[str]:
    records = [
        json.loads(line) for line in store.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return {topic for record in records if isinstance(topic := record.get("topic"), str)}


def _write_fake_claude(*, path: Path) -> None:
    script = path / "fake_claude.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys
            from pathlib import Path

            print("─── alpha ──")
            print("❯")
            print("──────")
            sys.stdout.flush()
            log = Path(sys.argv[1])
            for line in sys.stdin:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(line)
                print("─── alpha ──")
                print("❯")
                print("──────")
                sys.stdout.flush()
            """
        ).lstrip(),
        encoding="utf-8",
    )
    launcher = path / "claude"
    log = path / "fake-claude-input.log"
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        f"exec -a claude /usr/bin/python3 -u {shlex.quote(str(script))} "
        f'{shlex.quote(str(log))} "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)


def _run_foreman_act(
    *,
    context: ForemanActContext,
    proposal: dict[str, object],
    snapshot: dict[str, object],
) -> subprocess.CompletedProcess[str]:
    proposal_path = context.path / f"{proposal['topic']}-proposal.json"
    snapshot_path = context.path / f"{proposal['topic']}-snapshot.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    env = {
        **_scrubbed_env(),
        "HOME": str(context.home),
        "PATH": f"{context.path}:{os.environ['PATH']}",
        "TMUX": f"{context.socket},0,0",
    }
    return subprocess.run(  # noqa: S603
        [
            str(context.plugin_root / "bin" / "foreman-act"),
            "--proposal",
            str(proposal_path),
            "--snapshot-path",
            str(snapshot_path),
        ],
        cwd=context.repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )


def _assert_classifier_reports_occupied_name() -> None:
    classifier = importlib.import_module("foreman_session_classifier")
    signature = inspect.signature(classifier.classify_session_lifecycle)
    assert "occupied_tmux_sessions" in signature.parameters
    decision = classifier.classify_session_lifecycle(
        coordinates=classifier.SessionCoordinates(
            repo="/data/projects/livespec-overseer",
            topic="foreman",
            session_name="charter-gate-ratchet",
        ),
        snapshot=classifier.SnapshotEvidence(
            status="session-gone",
            runtime="codex",
            session_identity="none:/data/projects/livespec-overseer:foreman",
        ),
        live_sessions=(
            classifier.LiveSessionEvidence(
                runtime="codex",
                repo="/data/projects/livespec-overseer",
                session_name="unrelated-live-name",
                session_id="019fc11c-68c4-78c3-824b-d9b97de55a78",
            ),
        ),
        indexed_sessions=(
            classifier.IndexedSessionEvidence(
                runtime="codex",
                repo="/data/projects/livespec-overseer",
                session_name="unrelated-index-name",
                session_id="119fc11c-68c4-78c3-824b-d9b97de55a78",
                transcript_path="/home/me/.codex/sessions/2026/08/03/ignored.jsonl",
            ),
        ),
        occupied_tmux_sessions=("charter-gate-ratchet",),
    )
    assert decision.action == classifier.REPORT_ONLY
    assert decision.report is not None
    assert decision.report.reason == classifier.TMUX_SESSION_OCCUPIED


def _assert_act_refuses_occupied_start(*, repo: Path) -> None:
    module = importlib.import_module("foreman_act")
    original_tmux = module.tmuxio.TmuxIO
    calls: list[list[str]] = []

    class OccupiedTmux:
        def session_exists(self, *, session: str) -> bool:
            return session == "alpha"

    document = {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {"snapshot": {"status": "ok", "mode": "daemon-snapshot"}},
        "snapshot": _plan_start_snapshot(repo=repo, topic="alpha"),
        "dispatch_journal": [],
    }
    module.tmuxio.TmuxIO = OccupiedTmux
    try:
        result = module.act(
            proposal=_plan_start_proposal(repo=repo, topic="alpha"),
            gather=lambda *, repo, snapshot_path: document,
            run=lambda *, argv: calls.append(argv) or 0,
        )
    finally:
        module.tmuxio.TmuxIO = original_tmux

    assert result == {
        "action_id": "plan_start",
        "mutated": False,
        "outcome": "refused",
        "reason": "tmux_session_occupied",
    }
    assert calls == []


def _assert_foreman_start_guards_report_occupied_name(*, repo: Path) -> None:
    _assert_classifier_reports_occupied_name()
    _assert_act_refuses_occupied_start(repo=repo)


def test_every_plugin_bin_entrypoint_executes_help_from_clean_environment():
    entrypoints = sorted(path for path in PLUGIN_BIN.iterdir() if path.is_file())
    assert entrypoints, "plugin bin directory must ship executable entrypoints"

    failures: list[str] = []
    for entrypoint in entrypoints:
        completed = subprocess.run(  # noqa: S603
            [str(entrypoint), "--help"],
            cwd=ROOT,
            env=_scrubbed_env(),
            check=False,
            capture_output=True,
            text=True,
            timeout=15.0,
        )
        combined = completed.stdout + completed.stderr
        if completed.returncode != 0 or "Traceback" in combined:
            failures.append(
                f"{entrypoint.name} exited {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
            continue
        assert f"usage: {entrypoint.name}" in combined

    assert failures == []


def test_foreman_act_files_work_item_from_plugin_cache_without_caller_pythonpath(*, tmp_path):
    cache = tmp_path / "home" / ".claude" / "plugins" / "cache"
    overseer_plugin = _materialize_overseer_plugin(cache=cache)
    _materialize_orchestrator_plugin(cache=cache)
    repo = tmp_path / "repo"
    repo.mkdir()
    proposal_path = tmp_path / "proposal.json"
    snapshot_path = tmp_path / "snapshot.json"
    proposal_path.write_text(json.dumps(_work_item_file_proposal(repo=repo)), encoding="utf-8")
    snapshot_path.write_text(json.dumps(_status_snapshot(repo=repo)), encoding="utf-8")
    env = {**_scrubbed_env(), "HOME": str(tmp_path / "home")}

    completed = subprocess.run(  # noqa: S603
        [
            str(overseer_plugin / "bin" / "foreman-act"),
            "--proposal",
            str(proposal_path),
            "--snapshot-path",
            str(snapshot_path),
        ],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Traceback" not in completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {
        "action_id": "work_item_file",
        "mutated": True,
        "outcome": "acted",
        "reason": "filed:overseer-filed:ready",
    }
    assert json.loads((repo / "tmp" / "fake-intake.json").read_text(encoding="utf-8")) == {
        "above_floor": True,
        "item_id": "overseer-filed",
    }
    journal = repo / "tmp" / "fabro-dispatch-journal.jsonl"
    record = json.loads(journal.read_text(encoding="utf-8"))
    assert record["at"]
    assert record | {"at": None} == {
        "at": None,
        "stage": "foreman-act",
        "action_id": "work_item_file",
        "outcome": "acted",
        "reason": "filed:overseer-filed:ready",
        "mutated": True,
    }


def test_foreman_act_refuses_exact_occupied_tmux_start_from_shipped_artifact(*, tmp_path):
    plugin_root = _materialize_overseer_plugin(cache=tmp_path / "home" / ".claude/plugins/cache")
    repo = tmp_path / "repo"
    repo.mkdir()
    _assert_foreman_start_guards_report_occupied_name(repo=repo)
    home = tmp_path / "act-home"
    home.mkdir()
    socket = tmp_path / "tmux.sock"
    _write_fake_claude(path=tmp_path)
    context = ForemanActContext(
        plugin_root=plugin_root,
        repo=repo,
        home=home,
        socket=socket,
        path=tmp_path,
    )
    occupied_log = tmp_path / "occupied-input.log"
    occupied = (
        "python3 -u -c 'import sys, pathlib; "
        'print("OCCUPIED_READY", flush=True); '
        f"p=pathlib.Path({json.dumps(str(occupied_log))}); "
        '[p.open("a", encoding="utf-8").write(line) for line in sys.stdin]\''
    )
    try:
        created = _tmux(
            socket=socket,
            args=["new-session", "-d", "-s", "alpha", "-c", str(repo), occupied],
        )
        assert created.returncode == 0, created.stderr
        before_pid = _pane_pid(socket=socket, session="alpha")

        occupied_result = _run_foreman_act(
            context=context,
            proposal=_plan_start_proposal(repo=repo, topic="alpha"),
            snapshot=_plan_start_snapshot(repo=repo, topic="alpha"),
        )

        assert occupied_result.returncode == 0, occupied_result.stderr
        assert json.loads(occupied_result.stdout) == {
            "action_id": "plan_start",
            "mutated": False,
            "outcome": "refused",
            "reason": "tmux_session_occupied",
        }
        assert _pane_pid(socket=socket, session="alpha") == before_pid
        assert not occupied_log.exists()
        assert not (home / ".livespec-overseer.jsonl").exists()

        absent_result = _run_foreman_act(
            context=context,
            proposal=_plan_start_proposal(repo=repo, topic="beta"),
            snapshot=_plan_start_snapshot(repo=repo, topic="beta"),
        )

        assert absent_result.returncode == 0, absent_result.stderr
        assert json.loads(absent_result.stdout) == {
            "action_id": "plan_start",
            "mutated": True,
            "outcome": "acted",
            "reason": "started",
        }
        assert _tmux(socket=socket, args=["has-session", "-t", "=beta"]).returncode == 0
        assert "beta" in _registry_topics(store=home / ".livespec-overseer.jsonl")
    finally:
        _tmux(socket=socket, args=["kill-server"])
