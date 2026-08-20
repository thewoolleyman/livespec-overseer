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
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest
from foreman_act_types import SUPERVISOR_PAIR_START

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_BIN = ROOT / ".claude-plugin" / "bin"
PLUGIN_ROOT = ROOT / ".claude-plugin"
FOREMAN_PROSE = PLUGIN_ROOT / "prose" / "foreman.md"


@dataclass(frozen=True, kw_only=True)
class ForemanActContext:
    plugin_root: Path
    repo: Path
    home: Path
    socket: Path
    path: Path


@dataclass(frozen=True, kw_only=True)
class ForemanE2EContext:
    act: ForemanActContext
    sessions_dir: Path
    snapshot: dict[str, object]


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


def _with_snapshot_identity(
    *, proposal: dict[str, object], daemon_instance_id: str, tick_generation: int
) -> dict[str, object]:
    return {
        **proposal,
        "snapshot": {
            **dict(proposal["snapshot"]),
            "daemon_instance_id": daemon_instance_id,
            "tick_generation": tick_generation,
        },
    }


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


def _pane_capture(*, socket: Path, session: str) -> str:
    completed = _tmux(socket=socket, args=["capture-pane", "-p", "-t", session])
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def _wait_for_pane_capture(*, socket: Path, session: str, expected: str) -> str:
    deadline = time.monotonic() + 5.0
    capture = ""
    while time.monotonic() < deadline:
        capture = _pane_capture(socket=socket, session=session)
        if expected in capture:
            return capture
        time.sleep(0.05)
    return capture


def _pane_fingerprint(*, text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


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
            print("❯ pasted prompt")
            print("──────")
            print("─── alpha ──")
            print("❯")
            print("──────")
            sys.stdout.flush()
            log = Path(sys.argv[1])
            for line in sys.stdin:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(line)
                print("─── alpha ──")
                print("❯ pasted prompt")
                print("──────")
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


def _write_fake_codex(*, path: Path) -> None:
    launcher = path / "codex"
    log = path / "fake-codex-argv.jsonl"
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, time\n"
        "from pathlib import Path\n"
        f"log = Path({json.dumps(str(log))})\n"
        "log.open('a', encoding='utf-8').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "print('CODEX_READY', flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)


def _write_blocked_claude(*, path: Path) -> Path:
    launcher = path / "claude"
    shutil.copy2("/usr/bin/python3", launcher)
    launcher.chmod(0o755)
    log = path / "blocked-claude-input.log"
    script = path / "blocked_claude.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys
            from pathlib import Path

            log = Path(sys.argv[1])
            print("Approve the bounded retry?")
            print("❯ 1. Yes, proceed")
            print("  2. No, stop")
            sys.stdout.flush()
            for line in sys.stdin:
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(line)
                print("ANSWER_RECEIVED", flush=True)
            """
        ).lstrip(),
        encoding="utf-8",
    )
    return log


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


def _run_foreman_runtime(
    *,
    plugin_root: Path,
    repo: Path,
    home: Path,
    socket: Path,
    snapshot: dict[str, object],
    now: float,
) -> subprocess.CompletedProcess[str]:
    snapshot_path = home / "runtime-status.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    env = {
        **_scrubbed_env(),
        "HOME": str(home),
        "TMUX": f"{socket},0,0",
    }
    return subprocess.run(  # noqa: S603
        [
            str(plugin_root / "bin" / "foreman-runtime"),
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


def _render_foreman_document(
    *, plugin_root: Path, repo: Path, snapshot: dict[str, object], attention: dict[str, object]
) -> str:
    snapshot_path = repo / "status.json"
    attention_path = repo / "attention.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    attention_path.write_text(json.dumps(attention), encoding="utf-8")
    completed = subprocess.run(  # noqa: S603
        [
            str(plugin_root / "bin" / "foreman-gather"),
            "--repo",
            str(repo),
            "--snapshot-path",
            str(snapshot_path),
            "--journal-path",
            str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
            "--render",
        ],
        cwd=repo,
        env={
            **_scrubbed_env(),
            "PATH": os.environ["PATH"],
            "PYTHONPATH": "",
        },
        input=None,
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def _run_foreman_gather(
    *, plugin_root: Path, repo: Path, snapshot: dict[str, object]
) -> dict[str, object]:
    snapshot_path = repo / "status.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    completed = subprocess.run(  # noqa: S603
        [
            str(plugin_root / "bin" / "foreman-gather"),
            "--repo",
            str(repo),
            "--snapshot-path",
            str(snapshot_path),
            "--journal-path",
            str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
        ],
        cwd=repo,
        env={**_scrubbed_env(), "PYTHONPATH": ""},
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return parsed


def _run_foreman_consensus(
    *,
    plugin_root: Path,
    repo: Path,
    request: dict[str, object],
    reviewers: dict[str, object],
    state_dir: Path,
) -> dict[str, object]:
    request_path = repo / f"{request['item_id']}-request.json"
    reviewers_path = repo / f"{request['item_id']}-reviewers.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    reviewers_path.write_text(json.dumps(reviewers), encoding="utf-8")
    completed = subprocess.run(  # noqa: S603
        [
            str(plugin_root / "bin" / "foreman-consensus"),
            "--request",
            str(request_path),
            "--reviewer-responses",
            str(reviewers_path),
            "--state-dir",
            str(state_dir),
        ],
        cwd=repo,
        env={**_scrubbed_env(), "PYTHONPATH": ""},
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return parsed


def _foreman_e2e_context(*, tmp_path: Path) -> ForemanE2EContext:
    plugin_root = _materialize_overseer_plugin(cache=tmp_path / "home" / ".claude/plugins/cache")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "plan" / "alpha").mkdir(parents=True)
    (repo / "plan" / "alpha" / "handoff.md").write_text("alpha handoff\n", encoding="utf-8")
    (repo / "plan" / "beta").mkdir(parents=True)
    (repo / "plan" / "beta" / "supervisor-handoff.md").write_text(
        "beta supervisor handoff\n", encoding="utf-8"
    )
    (repo / "tmp").mkdir()
    home = tmp_path / "runtime-home"
    sessions_dir = home / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True)
    (home / ".livespec-overseer-repos.json").write_text(
        json.dumps({"repos": [str(repo)]}) + "\n", encoding="utf-8"
    )
    _write_fake_claude(path=tmp_path)
    _write_fake_codex(path=tmp_path)
    return ForemanE2EContext(
        act=ForemanActContext(
            plugin_root=plugin_root,
            repo=repo,
            home=home,
            socket=tmp_path / "tmux.sock",
            path=tmp_path,
        ),
        sessions_dir=sessions_dir,
        snapshot=_foreman_e2e_snapshot(repo=repo),
    )


def _foreman_e2e_snapshot(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "daemon_instance_id": "daemon-e2e",
        "tick_generation": 1,
        "written_at": "2026-08-04T08:00:00Z",
        "rows": [
            {
                "repo": str(repo),
                "topic": "alpha",
                "tmux": "alpha",
                "runtime": "codex",
                "status": "session-gone",
                "session_identity": f"none:{repo}:alpha",
            },
            {
                "repo": str(repo),
                "topic": "beta",
                "tmux": "beta-supervisor",
                "runtime": "codex",
                "status": "session-gone",
                "session_identity": f"none:{repo}:beta-supervisor",
            },
            {
                "repo": str(repo),
                "topic": "gamma-supervisor",
                "tmux": "gamma-supervisor",
                "runtime": "codex",
                "status": "session-gone",
                "session_identity": f"none:{repo}:gamma-supervisor",
            },
        ],
    }


def _e2e_plan_start_proposal(*, repo: Path, topic: str) -> dict[str, object]:
    return _with_snapshot_identity(
        proposal=_plan_start_proposal(repo=repo, topic=topic),
        daemon_instance_id="daemon-e2e",
        tick_generation=1,
    )


def _e2e_supervisor_pair_proposal(*, repo: Path) -> dict[str, object]:
    proposal = _e2e_plan_start_proposal(repo=repo, topic="beta")
    proposal["action_id"] = "supervisor_pair_start"
    proposal["session_name"] = "beta-supervisor"
    snapshot = proposal["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["session_identity"] = f"none:{repo}:beta-supervisor"
    classifier = proposal["classifier"]
    assert isinstance(classifier, dict)
    start = classifier["start"]
    assert isinstance(start, dict)
    start["session_name"] = "beta-supervisor"
    return proposal


def _e2e_attention() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-04T08:00:00Z",
        "items": [
            {
                "id": "overseer-e2e7",
                "kind": "work-item",
                "session_name": "overseer-e2e7",
                "title": "needs human-facing session",
            }
        ],
    }


def _blocked_attention() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-05T22:10:00Z",
        "items": [
            {
                "id": "overseer-ctc",
                "kind": "blocked-session",
                "session_name": "blocked-alpha",
                "tmux": "blocked-alpha",
                "title": "blocked on bounded retry approval",
            }
        ],
    }


def _blocked_snapshot(*, repo: Path, pane_content_hash: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "daemon_instance_id": "daemon-e2e",
        "tick_generation": 5,
        "written_at": "2026-08-05T22:10:00Z",
        "needs_attention": _blocked_attention(),
        "rows": [
            {
                "repo": str(repo),
                "topic": "blocked-alpha",
                "tmux": "blocked-alpha",
                "runtime": "claude",
                "status": "blocked:human",
                "session_identity": "claude:blocked-alpha-session",
                "pane_content_hash": pane_content_hash,
                "note": "structured gate on pane",
            }
        ],
    }


def _blocked_consensus_request(
    *, repo: Path, question: str = "Should the blocked alpha session proceed?"
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "blocked_question": question,
        "repo": str(repo),
        "topic": "blocked-alpha",
        "tmux": "blocked-alpha",
        "item_id": "overseer-ctc",
        "repo_revision": "abc123",
        "item_revision": "status:blocked/rank:seed-5",
        "handoff_or_work_item": "Answer the existing blocked prompt only if consensus holds.",
        "repo_context": "livespec-overseer shipped-plugin E2E",
        "snapshot": {
            "daemon_instance_id": "daemon-e2e",
            "tick_generation": 5,
            "session_identity": "claude:blocked-alpha-session",
        },
    }


def _blocked_answer_reviewers(*, dissent: bool = False) -> dict[str, object]:
    action = {
        "action_id": "blocked_session_answer",
        "params": {"mode": "answer_existing_prompt"},
    }
    reviewers: list[dict[str, object]] = [
        {"reviewer_id": "fable", "verdict": "unblock", "action": action},
        {"reviewer_id": "opus", "verdict": "unblock", "action": action},
        {"reviewer_id": "gpt-sol", "verdict": "unblock", "action": action},
    ]
    if dissent:
        reviewers[2] = {
            "reviewer_id": "gpt-sol",
            "verdict": "needs-human",
            "action": {"action_id": "human_valve", "params": {"reason": "cross-vendor veto"}},
        }
    return {"reviewers": reviewers}


def _blocked_answer_proposal(
    *,
    repo: Path,
    request: dict[str, object],
    reviewers: dict[str, object],
    question_fingerprint: str,
    answer: str = "Yes, proceed with the bounded retry.",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": "blocked_session_answer",
        "repo": str(repo),
        "topic": "blocked-alpha",
        "session_name": "blocked-alpha",
        "snapshot": {
            "daemon_instance_id": "daemon-e2e",
            "tick_generation": 5,
            "session_identity": "claude:blocked-alpha-session",
        },
        "classifier": {"action": "answer_existing_prompt"},
        "human_valve": {"category": "ordinary"},
        "consensus": {"request": request, "reviewer_responses": reviewers},
        "blocked_session_answer": {
            "mode": "answer_existing_prompt",
            "answer_text": answer,
            "question_fingerprint": question_fingerprint,
        },
    }


def _e2e_work_item_proposal(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": "work_item_session_start",
        "repo": str(repo),
        "topic": "overseer-e2e7",
        "session_name": "overseer-e2e7",
        "snapshot": {"daemon_instance_id": "daemon-e2e", "tick_generation": 1},
        "classifier": {"action": "start"},
        "work_item_session": {
            "work_item_id": "overseer-e2e7",
            "session_name": "overseer-e2e7",
            "handoff": "bounded one-shot handoff\n",
        },
    }


def _assert_plan_and_supervisor_sessions(*, context: ForemanE2EContext) -> None:
    plan = _run_foreman_act(
        context=context.act,
        proposal=_e2e_plan_start_proposal(repo=context.act.repo, topic="alpha"),
        snapshot=context.snapshot,
    )
    assert plan.returncode == 0, plan.stderr
    assert json.loads(plan.stdout)["reason"] == "started"
    assert _tmux(socket=context.act.socket, args=["has-session", "-t", "=alpha"]).returncode == 0

    supervisor = _run_foreman_act(
        context=context.act,
        proposal=_e2e_supervisor_pair_proposal(repo=context.act.repo),
        snapshot=context.snapshot,
    )
    assert supervisor.returncode == 0, supervisor.stderr
    assert json.loads(supervisor.stdout)["reason"] == "started"
    assert (
        _tmux(socket=context.act.socket, args=["has-session", "-t", "=beta-supervisor"]).returncode
        == 0
    )


def _assert_work_item_lifecycle(*, context: ForemanE2EContext) -> None:
    proposal = _e2e_work_item_proposal(repo=context.act.repo)
    attention = _e2e_attention()
    snapshot = {**context.snapshot, "rows": [], "needs_attention": attention}
    started = _run_foreman_act(context=context.act, proposal=proposal, snapshot=snapshot)
    assert started.returncode == 0, started.stderr
    assert json.loads(started.stdout)["reason"] == "work_item_session_started"
    assert (
        _tmux(socket=context.act.socket, args=["has-session", "-t", "=overseer-e2e7"]).returncode
        == 0
    )
    state_dir = context.act.repo / "tmp" / "overseer" / "foreman" / "work-items" / "overseer-e2e7"
    assert json.loads((state_dir / "claim.json").read_text(encoding="utf-8")) == {
        "attempt": 1,
        "session_name": "overseer-e2e7",
        "work_item_id": "overseer-e2e7",
    }
    assert (state_dir / "handoff.md").read_text(encoding="utf-8") == ("bounded one-shot handoff\n")
    finish = {**proposal, "action_id": "work_item_session_finish"}
    finish_payload = finish["work_item_session"]
    assert isinstance(finish_payload, dict)
    finish_payload["terminal"] = {"status": "completed", "reason": "done"}
    finished = _run_foreman_act(context=context.act, proposal=finish, snapshot=snapshot)
    assert finished.returncode == 0, finished.stderr
    assert json.loads(finished.stdout)["reason"] == "work_item_session_completed"
    assert not (state_dir / "claim.json").exists()
    outcome = json.loads((state_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["status"] == "completed"


def _assert_lifecycle_sabotage_discriminates(*, context: ForemanE2EContext) -> None:
    occupied = _run_foreman_act(
        context=context.act,
        proposal=_e2e_plan_start_proposal(repo=context.act.repo, topic="alpha"),
        snapshot=context.snapshot,
    )
    assert json.loads(occupied.stdout)["reason"] == "tmux_session_occupied"
    ambiguous = {
        **_e2e_supervisor_pair_proposal(repo=context.act.repo),
        "snapshot": {"daemon_instance_id": "other", "tick_generation": 1},
    }
    refused = _run_foreman_act(context=context.act, proposal=ambiguous, snapshot=context.snapshot)
    assert json.loads(refused.stdout)["reason"] == "daemon_identity_changed"


def _assert_needs_you_render(*, context: ForemanE2EContext) -> None:
    rendered = _render_foreman_document(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        snapshot=context.snapshot,
        attention=_e2e_attention(),
    )
    expected = (
        "\nNEEDS YOU:\n"
        "  overseer-e2e7 | overseer-e2e7 | work-item | needs human-facing session\n"
    )
    assert expected in rendered
    resolved = _render_foreman_document(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        snapshot=context.snapshot,
        attention={"schema_version": 1, "items": []},
    )
    assert "\nNEEDS YOU:\n  none\n" in resolved


def _assert_supervisor_handoff_signal_from_shipped_gather(*, context: ForemanE2EContext) -> None:
    document = _run_foreman_gather(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        snapshot=context.snapshot,
    )
    rendered = _render_foreman_document(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        snapshot=context.snapshot,
        attention={"schema_version": 1, "items": []},
    )

    def assert_distinguishable(*, rows: list[dict[str, object]], text: str) -> None:
        by_topic = {str(row.get("topic")): row for row in rows}
        assert by_topic["alpha"]["supervisor_handoff"] == "missing"
        assert by_topic["beta"]["supervisor_handoff"] == "present"
        assert by_topic["gamma-supervisor"]["supervisor_handoff"] == "supervisor-topic"
        assert "alpha | session-gone | ctx=None | human_wait=no | supervisor=missing" in text
        assert "beta | session-gone | ctx=None | human_wait=no | supervisor=present" in text
        assert (
            "gamma-supervisor | session-gone | ctx=None | human_wait=no | "
            "supervisor=supervisor-topic"
        ) in text

    snapshot = document["snapshot"]
    assert isinstance(snapshot, dict)
    rows = snapshot["rows"]
    assert isinstance(rows, list)
    assert all(isinstance(row, dict) for row in rows)
    assert_distinguishable(rows=rows, text=rendered)

    stripped_rows = [
        {key: value for key, value in row.items() if key != "supervisor_handoff"} for row in rows
    ]
    with pytest.raises(KeyError):
        assert_distinguishable(rows=stripped_rows, text=rendered)


def _supervisor_pair_guidance_errors(*, text: str) -> list[str]:
    required = (
        SUPERVISOR_PAIR_START,
        "supervisor_handoff",
        "missing",
        "plan/<topic>/supervisor-handoff.md",
        "operator asked",
    )
    return [term for term in required if term not in text]


def _assert_supervisor_pair_contract_guidance_is_tree_derived() -> None:
    text = FOREMAN_PROSE.read_text(encoding="utf-8")

    assert _supervisor_pair_guidance_errors(text=text) == []
    sabotaged = text.replace("supervisor_handoff", "")
    assert _supervisor_pair_guidance_errors(text=sabotaged) == ["supervisor_handoff"]


def _prepare_blocked_session(*, context: ForemanE2EContext) -> tuple[Path, dict[str, object]]:
    log = _write_blocked_claude(path=context.act.path)
    (context.act.repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"foreman_valve_disposition": "consensus"}}),
        encoding="utf-8",
    )
    created = _tmux(
        socket=context.act.socket,
        args=[
            "new-session",
            "-d",
            "-s",
            "blocked-alpha",
            "-c",
            str(context.act.repo),
            str(context.act.path / "claude"),
            "-u",
            str(context.act.path / "blocked_claude.py"),
            str(log),
        ],
    )
    assert created.returncode == 0, created.stderr
    capture = _wait_for_pane_capture(
        socket=context.act.socket,
        session="blocked-alpha",
        expected="Approve the bounded retry?",
    )
    assert "Approve the bounded retry?" in capture
    snapshot = _blocked_snapshot(
        repo=context.act.repo,
        pane_content_hash=_pane_fingerprint(text=capture),
    )
    (context.act.repo / "attention.json").write_text(
        json.dumps(_blocked_attention()), encoding="utf-8"
    )
    return log, snapshot


def _assert_blocked_dossier_and_attention(
    *, context: ForemanE2EContext, snapshot: dict[str, object]
) -> None:
    dossier = _run_foreman_gather(
        plugin_root=context.act.plugin_root, repo=context.act.repo, snapshot=snapshot
    )
    rows = dossier["snapshot"]["rows"]
    assert isinstance(rows, list)
    assert rows[0]["status"] == "blocked:human"
    assert rows[0]["tmux"] == "blocked-alpha"
    assert dossier["needs_attention"] == _blocked_attention()
    rendered = _render_foreman_document(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        snapshot=snapshot,
        attention=_blocked_attention(),
    )
    assert "\nNEEDS YOU:\n  overseer-ctc | blocked-alpha | blocked-session | " in rendered


def _assert_unanimous_blocked_answer_act(
    *, context: ForemanE2EContext, snapshot: dict[str, object], log: Path
) -> None:
    request = _blocked_consensus_request(repo=context.act.repo)
    reviewers = _blocked_answer_reviewers()
    question_fingerprint = str(snapshot["rows"][0]["pane_content_hash"])
    verdict = _run_foreman_consensus(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        request=request,
        reviewers=reviewers,
        state_dir=context.act.repo / "tmp" / "panel-state",
    )
    assert verdict["outcome"] == "unanimous"
    assert verdict["action"] == {
        "action_id": "blocked_session_answer",
        "params": {"mode": "answer_existing_prompt"},
    }
    assert [model["vendor"] for model in verdict["models"]] == ["anthropic", "anthropic", "openai"]
    assert [model["model"] for model in verdict["models"]] == [
        "claude-fable-5",
        "claude-opus-5",
        "gpt-5.6-sol",
    ]

    acted = _run_foreman_act(
        context=context.act,
        proposal=_blocked_answer_proposal(
            repo=context.act.repo,
            request=request,
            reviewers=reviewers,
            question_fingerprint=question_fingerprint,
        ),
        snapshot=snapshot,
    )
    assert acted.returncode == 0, acted.stderr
    assert json.loads(acted.stdout) == {
        "action_id": "blocked_session_answer",
        "mutated": True,
        "outcome": "acted",
        "reason": "answered_existing_prompt",
    }
    assert "Yes, proceed with the bounded retry.\n" in log.read_text(encoding="utf-8")
    journal = [
        json.loads(line)
        for line in (context.act.repo / "tmp" / "fabro-dispatch-journal.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert journal[-2]["stage"] == "foreman-consensus-act"
    assert journal[-2]["authorized_action_id"] == "blocked_session_answer"
    assert journal[-2]["panel_outcome"] == "unanimous"
    assert journal[-1]["stage"] == "foreman-act"
    assert journal[-1]["reason"] == "answered_existing_prompt"


def _assert_blocked_consensus_sabotage_refuses(
    *, context: ForemanE2EContext, snapshot: dict[str, object], log: Path
) -> None:
    sabotage_request = _blocked_consensus_request(
        repo=context.act.repo,
        question="Should a non-Anthropic dissent be overridden?",
    )
    sabotage_reviewers = _blocked_answer_reviewers(dissent=True)
    sabotage_verdict = _run_foreman_consensus(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        request=sabotage_request,
        reviewers=sabotage_reviewers,
        state_dir=context.act.repo / "tmp" / "sabotage-panel-state",
    )
    assert sabotage_verdict["outcome"] == "escalate"
    assert sabotage_verdict["reason"] == "non_anthropic_needs_human_dissent"
    refused = _run_foreman_act(
        context=context.act,
        proposal=_blocked_answer_proposal(
            repo=context.act.repo,
            request=sabotage_request,
            reviewers=sabotage_reviewers,
            question_fingerprint=str(snapshot["rows"][0]["pane_content_hash"]),
            answer="SABOTAGE SHOULD NOT PASTE",
        ),
        snapshot=snapshot,
    )
    assert refused.returncode == 0, refused.stderr
    assert json.loads(refused.stdout) == {
        "action_id": "blocked_session_answer",
        "mutated": False,
        "outcome": "refused",
        "reason": "consensus_not_unanimous:non_anthropic_needs_human_dissent",
    }
    assert "SABOTAGE SHOULD NOT PASTE" not in log.read_text(encoding="utf-8")


def _assert_blocked_consensus_chain(*, context: ForemanE2EContext) -> None:
    log, snapshot = _prepare_blocked_session(context=context)
    _assert_blocked_dossier_and_attention(context=context, snapshot=snapshot)
    _assert_unanimous_blocked_answer_act(context=context, snapshot=snapshot, log=log)
    _assert_blocked_consensus_sabotage_refuses(context=context, snapshot=snapshot, log=log)


def _register_foreman_session(*, context: ForemanE2EContext) -> None:
    created = _tmux(
        socket=context.act.socket,
        args=[
            "new-session",
            "-d",
            "-s",
            "repo-foreman",
            "-c",
            str(context.act.repo),
            "sleep 60",
        ],
    )
    assert created.returncode == 0, created.stderr
    pane_pid = _pane_pid(socket=context.act.socket, session="repo-foreman")
    proc_start = (Path("/proc") / pane_pid / "stat").read_text(encoding="utf-8").split()[21]
    (context.sessions_dir / f"{pane_pid}.json").write_text(
        json.dumps(
            {
                "pid": int(pane_pid),
                "name": "repo-foreman",
                "cwd": str(context.act.repo),
                "status": "idle",
                "procStart": proc_start,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _runtime_result(
    *, context: ForemanE2EContext, snapshot: dict[str, object], now: float
) -> dict[str, object]:
    completed = _run_foreman_runtime(
        plugin_root=context.act.plugin_root,
        repo=context.act.repo,
        home=context.act.home,
        socket=context.act.socket,
        snapshot=snapshot,
        now=now,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _run_foreman_runtime_resume(
    *, context: ForemanE2EContext, snapshot: dict[str, object], now: float
) -> subprocess.CompletedProcess[str]:
    snapshot_path = context.act.home / "runtime-status.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    env = {
        **_scrubbed_env(),
        "HOME": str(context.act.home),
        "TMUX": f"{context.act.socket},0,0",
    }
    return subprocess.run(  # noqa: S603
        [
            str(context.act.plugin_root / "bin" / "foreman-runtime"),
            "--repo",
            str(context.act.repo),
            "--watch-set-path",
            str(context.act.home / ".livespec-overseer-repos.json"),
            "--snapshot-path",
            str(snapshot_path),
            "--now-epoch",
            str(now),
            "--resume",
        ],
        cwd=context.act.repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30.0,
    )


def _runtime_state(*, context: ForemanE2EContext, name: str) -> dict[str, object]:
    return json.loads(
        (context.act.repo / "tmp" / "overseer" / "foreman" / name).read_text(encoding="utf-8")
    )


def _assert_runtime_cadence(*, context: ForemanE2EContext) -> None:
    _register_foreman_session(context=context)
    snapshot = {**context.snapshot, "rows": [context.snapshot["rows"][0]]}
    first = _runtime_result(context=context, snapshot=snapshot, now=1000.0)
    assert first == {
        "action_taken": False,
        "exit_reason": None,
        "heartbeat_age_seconds": None,
        "llm_tick": True,
        "loop_lapsed": False,
        "tick_generation": 1,
    }
    assert _runtime_state(context=context, name="runtime.json")["next_llm_tick_at"] == 4600.0
    assert _runtime_result(context=context, snapshot=snapshot, now=1001.0)["exit_reason"] is None
    changed = {**snapshot, "tick_generation": 2}
    assert _runtime_result(context=context, snapshot=changed, now=4600.0)["exit_reason"] == (
        "converged"
    )
    assert _runtime_result(context=context, snapshot=changed, now=8200.0)["exit_reason"] == (
        "converged"
    )
    assert _runtime_state(context=context, name="heartbeat.json")["tick_interval_seconds"] == 3600
    assert _runtime_state(context=context, name="runtime.json")["last_generation_fingerprint"]

    resumed = _run_foreman_runtime_resume(context=context, snapshot=changed, now=8201.0)
    assert resumed.returncode == 0, resumed.stderr
    assert _runtime_state(context=context, name="runtime.json") == {
        **_runtime_state(context=context, name="runtime.json"),
        "tick_generation": 0,
        "next_llm_tick_at": 0.0,
        "stable_ticks": 0,
    }


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
    (repo / "plan" / "alpha").mkdir(parents=True)
    (repo / "plan" / "beta").mkdir(parents=True)
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


def test_shipped_foreman_e2e_covers_seed_session_attention_and_cadence(*, tmp_path):
    context = _foreman_e2e_context(tmp_path=tmp_path)
    try:
        _assert_plan_and_supervisor_sessions(context=context)
        _assert_work_item_lifecycle(context=context)
        _assert_blocked_consensus_chain(context=context)
        _assert_lifecycle_sabotage_discriminates(context=context)
        _assert_needs_you_render(context=context)
        _assert_supervisor_handoff_signal_from_shipped_gather(context=context)
        _assert_supervisor_pair_contract_guidance_is_tree_derived()
        _assert_runtime_cadence(context=context)
    finally:
        _tmux(socket=context.act.socket, args=["kill-server"])
