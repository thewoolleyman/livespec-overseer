"""Executable E2E gate for every shipped plugin ``bin/`` launcher."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_BIN = ROOT / ".claude-plugin" / "bin"
PLUGIN_ROOT = ROOT / ".claude-plugin"


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
