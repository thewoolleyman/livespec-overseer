"""Tests for foreman_act.py — deterministic Phase B lifecycle acts."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_act.py"
EXECUTABLE_PATH = OVERSEER_DIR / "foreman-act"
PANE_CLAIM_PATH = OVERSEER_DIR / "foreman_pane_claim.py"
GATE_STATE_PATH = OVERSEER_DIR / "foreman_gate_state.py"

__all__: list[str] = []


def foreman_act():
    assert MODULE_PATH.is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act")


def foreman_act_filing():
    assert (OVERSEER_DIR / "foreman_act_filing.py").is_file()
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act_filing")


def module(name: str):
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module(name)


def base_document(*, repo: Path, generation: int = 7) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {"snapshot": {"status": "ok", "mode": "daemon-snapshot"}},
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": generation,
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
        },
        "dispatch_journal": [],
    }


def blocked_document(*, repo: Path, runtime: str = "claude") -> dict[str, object]:
    document = base_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row.update(
        {
            "runtime": runtime,
            "status": "blocked:human",
            "session_identity": f"{runtime}:session-1",
            "question_fingerprint": "question-1",
            "note": "structured gate on pane",
        }
    )
    return document


def start_proposal(*, repo: Path, action_id: str = "plan_start") -> dict[str, object]:
    return {
        "schema_version": 1,
        "action_id": action_id,
        "repo": str(repo),
        "topic": "alpha",
        "session_name": "alpha",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": f"none:{repo}:alpha",
        },
        "classifier": {
            "action": "start",
            "start": {"repo": str(repo), "topic": "alpha", "session_name": "alpha"},
        },
    }


def blocked_answer_proposal(
    *, repo: Path, mode: str = "answer_existing_prompt"
) -> dict[str, object]:
    proposal = start_proposal(repo=repo, action_id="blocked_session_answer")
    proposal["snapshot"] = {
        "daemon_instance_id": "daemon-1",
        "tick_generation": 7,
        "session_identity": "claude:session-1",
    }
    proposal["human_valve"] = {"category": "ordinary"}
    proposal["consensus"] = {
        "request": {"item_id": "overseer-0fy", "choice": "answer alpha"},
        "reviewer_responses": {},
    }
    proposal["blocked_session_answer"] = {
        "mode": mode,
        "answer_text": "Yes, proceed with the bounded retry.",
        "question_fingerprint": "question-1",
    }
    return proposal


def blocked_answer_panel_result() -> dict[str, object]:
    reviewers = [
        {
            "reviewer_id": "fable",
            "model": {"reviewer_id": "fable", "vendor": "anthropic", "model": "claude-fable-5"},
            "verdict": "unblock",
            "action": {"action_id": "blocked_session_answer", "params": {}},
        },
        {
            "reviewer_id": "opus",
            "model": {"reviewer_id": "opus", "vendor": "anthropic", "model": "claude-opus-5"},
            "verdict": "unblock",
            "action": {"action_id": "blocked_session_answer", "params": {}},
        },
        {
            "reviewer_id": "gpt-sol",
            "model": {"reviewer_id": "gpt-sol", "vendor": "openai", "model": "gpt-5.6-sol"},
            "verdict": "unblock",
            "action": {"action_id": "blocked_session_answer", "params": {}},
        },
    ]
    return {
        "schema_version": 1,
        "outcome": "unanimous",
        "reason": "three_typed_actions_equal",
        "action": {"action_id": "blocked_session_answer", "params": {}},
        "reviewers": reviewers,
        "models": [reviewer["model"] for reviewer in reviewers],
        "cache_key": "answer-cache",
        "mutated": False,
    }


def _pane_fingerprint(*, text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def write_consensus_config(*, repo: Path) -> None:
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": {"foreman_valve_disposition": "consensus"}}),
        encoding="utf-8",
    )


def resume_proposal(*, repo: Path) -> dict[str, object]:
    proposal = start_proposal(repo=repo, action_id="qualifying_session_resume")
    proposal["snapshot"] = {
        "daemon_instance_id": "daemon-1",
        "tick_generation": 7,
        "session_identity": "codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
    }
    proposal["classifier"] = {
        "action": "exact_resume",
        "resume": {
            "runtime": "codex",
            "repo": str(repo),
            "topic": "alpha",
            "session_name": "alpha",
            "session_id": "019fc11c-68c4-78c3-824b-d9b97de55a78",
            "transcript_path": "/home/me/.codex/sessions/rollout.jsonl",
        },
    }
    return proposal


def file_proposal(*, repo: Path, target_repo: Path | None = None) -> dict[str, object]:
    proposal = start_proposal(repo=repo, action_id="work_item_file")
    proposal["filing"] = {
        "target_repo": str(target_repo or repo),
        "title": "File the delegated fix",
        "description": "Capture this follow-up through intake.",
        "type": "feature",
        "assignee": None,
        "depends_on": [{"kind": "local", "work_item_id": "overseer-parent"}],
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
    }
    return proposal


def journal_record(*, work_item_id: str = "overseer-a") -> dict[str, object]:
    return {
        "stage": "outcome",
        "outcome": {
            "work_item_id": work_item_id,
            "status": "failed",
            "stage": "merge-poll",
            "pr_number": 630,
            "merge_sha": "ad76472",
            "detail": "PR merged after the poll budget.",
            "fabro_run_id": "01KZ4",
        },
    }


def journal_document(*, repo: Path, records: list[dict[str, object]]) -> dict[str, object]:
    document = base_document(repo=repo)
    document["sources"] = {
        **document["sources"],
        "dispatch_journal": {
            "status": "ok",
            "path": str(repo / "tmp" / "fabro-dispatch-journal.jsonl"),
            "records_read": len(records),
        },
    }
    document["dispatch_journal"] = records
    return document


def reconcile_proposal(*, repo: Path, record: dict[str, object]) -> dict[str, object]:
    proposal = start_proposal(repo=repo, action_id="dispatch_journal_reconcile_merged")
    proposal["dispatch_journal"] = {
        "records_read": 1,
        "record": record,
    }
    proposal["dispatcher"] = {"path": str(repo / ".orchestrator" / "bin" / "dispatcher.py")}
    return proposal


def test_foreman_act_module_executable_and_closed_schema_exist():
    module = foreman_act()

    assert EXECUTABLE_PATH.is_file()
    assert EXECUTABLE_PATH.stat().st_mode & 0o111
    assert module.PROPOSAL_SCHEMA_VERSION == 1
    assert module.ACTION_IDS == (
        "blocked_session_answer",
        "dispatch_journal_reconcile_merged",
        "human_valve",
        "plan_start",
        "qualifying_session_resume",
        "qualifying_session_start",
        "supervisor_pair_start",
        "work_item_file",
        "work_item_session_finish",
        "work_item_session_resume",
        "work_item_session_start",
    )


def test_plan_start_uses_absolute_overseer_start_command(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    result = module.act(
        proposal=start_proposal(repo=repo),
        gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
        run=lambda *, argv: calls.append(argv) or 0,
    )

    assert result == {
        "action_id": "plan_start",
        "mutated": True,
        "outcome": "acted",
        "reason": "started",
    }
    assert calls == [
        [
            sys.executable,
            str(OVERSEER_DIR / "supervisor.py"),
            "start",
            "--repo",
            str(repo),
            "--topic",
            "alpha",
        ]
    ]


def test_supervisor_pair_start_uses_migrated_supervisor_ledger_anchor(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    plan = repo / "plan" / "alpha"
    plan.mkdir(parents=True)
    (plan / "epic.md").write_text(
        "# Plan Epic\n\n"
        "Ledger epic anchor: `overseer-test-epic`\n\n"
        "The supervisor binder is read from attributed ledger comments.\n",
        encoding="utf-8",
    )
    proposal = start_proposal(repo=repo, action_id="supervisor_pair_start")
    proposal["session_name"] = "alpha-supervisor"
    snapshot = proposal["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["session_identity"] = f"none:{repo}:alpha-supervisor"
    classifier = proposal["classifier"]
    assert isinstance(classifier, dict)
    start = classifier["start"]
    assert isinstance(start, dict)
    start["session_name"] = "alpha-supervisor"
    document = base_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["session_identity"] = f"none:{repo}:alpha-supervisor"
    calls: list[list[str]] = []

    result = module.act(
        proposal=proposal,
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: calls.append(argv) or 0,
    )

    assert result["reason"] == "started"
    assert calls == [
        [
            "tmux",
            "new-session",
            "-d",
            "-s",
            "alpha-supervisor",
            "-c",
            str(repo),
            "claude",
            "--dangerously-skip-permissions",
            "-n",
            "alpha-supervisor",
            f"resume supervisor entity alpha-supervisor for plan epic overseer-test-epic "
            f"in repository {repo}; read the supervisor handoff entries attributed to "
            "that entity",
        ]
    ]
    assert not (plan / "supervisor-handoff.md").exists()


def test_supervisor_resume_uses_ledger_even_when_legacy_handoff_exists(*, tmp_path):
    repo = tmp_path / "repo"
    topic = "alpha"
    plan = repo / "plan" / topic
    plan.mkdir(parents=True)
    (plan / "supervisor-handoff.md").write_text("retired file-shaped binder\n", encoding="utf-8")
    prompts = module("_supervisor_prompts")

    text = prompts.supervisor_resume(repo=str(repo), topic=topic, epic="overseer-test-epic")

    assert "overseer-test-epic" in text
    assert str(repo) in text
    assert "alpha-supervisor" in text
    assert "supervisor handoff entries attributed to that entity" in text
    assert "supervisor-handoff.md" not in text


def test_supervisor_prompt_resume_builders_cover_ledger_and_no_epic_shapes(*, tmp_path):
    prompts = module("_supervisor_prompts")
    registry = module("registry")
    repo = str(tmp_path / "repo")
    topic = "alpha"
    epic = "overseer-test-epic"
    worker = registry.Track(topic=topic, repo=repo, tmux=topic, epic=epic)
    worker_without_epic = registry.Track(topic=topic, repo=repo, tmux=topic, epic=None)
    supervisor = registry.Track(
        topic=f"{topic}-supervisor", repo=repo, tmux=f"{topic}-supervisor", epic=epic
    )
    supervisor_without_epic = registry.Track(
        topic=f"{topic}-supervisor", repo=repo, tmux=f"{topic}-supervisor", epic=None
    )

    assert prompts.plan_state_locator(repo=repo, epic=None).count("NO plan epic id") == 1
    assert prompts.plan_state_locator(repo=repo, epic=epic) == (
        f"the plan state held on ledger epic {epic} in repository {repo}"
    )
    assert prompts.plan_epic_resume(repo=repo, epic=epic) == (
        f"resume plan epic {epic} in repository {repo}; read its ledger-held plan state"
    )
    assert prompts.resume_for_track(track=worker) == prompts.plan_epic_resume(repo=repo, epic=epic)
    assert prompts.resume_for_track(track=worker_without_epic) is None
    assert prompts.resume_for_track(track=supervisor) == prompts.supervisor_ledger_resume(
        repo=repo, topic=topic, epic=epic
    )
    supervisor_without_epic_resume = prompts.resume_for_track(track=supervisor_without_epic)
    assert supervisor_without_epic_resume is not None
    assert "NO plan epic id" in supervisor_without_epic_resume
    assert prompts.launch_resume(track=worker) == prompts.plan_epic_resume(repo=repo, epic=epic)
    assert "no plan epic id is recorded" in prompts.launch_resume(track=worker_without_epic)
    assert (
        prompts.supervisor_handoff_path(repo=repo, topic=topic)
        .as_posix()
        .endswith("/plan/alpha/supervisor-handoff.md")
    )
    assert (
        prompts.supervisor_epic_path(repo=repo, topic=topic)
        .as_posix()
        .endswith("/plan/alpha/epic.md")
    )


def test_foreman_prompt_resume_builder_covers_ledger_and_no_epic_shapes(*, tmp_path):
    prompts = module("_supervisor_prompts")
    repo = str(tmp_path / "repo")
    epic = "overseer-foreman-epic"

    assert hasattr(prompts, "foreman_resume")
    foreman_resume = prompts.foreman_resume(repo=repo, epic=epic)

    assert foreman_resume == (
        f"resume foreman ledger epic {epic} in repository {repo}; "
        "read its ledger-held foreman handoff timeline"
    )
    assert repo in foreman_resume
    assert epic in foreman_resume
    assert "plan/" not in foreman_resume
    foreman_resume_without_epic = prompts.foreman_resume(repo=repo, epic=None)
    assert "NO foreman ledger epic id" in foreman_resume_without_epic
    assert repo in foreman_resume_without_epic
    assert "plan/" not in foreman_resume_without_epic


def test_foreman_resume_command_uses_ledger_prompt_instead_of_scratch_handoff(*, tmp_path):
    commands = module("foreman_act_commands")
    repo = str(tmp_path / "repo")
    epic = "overseer-foreman-epic"
    handoff = f"{repo}/tmp/overseer/foreman/foreman-session-handoff.md"

    command = commands.resume_command_from_payload(
        payload={
            "runtime": "codex",
            "repo": repo,
            "topic": "repo-foreman",
            "session_id": "codex-session-id",
            "handoff_path": handoff,
            "epic": epic,
        }
    )

    assert command is not None
    prompt = command[-1]
    assert prompt == (
        f"resume foreman ledger epic {epic} in repository {repo}; "
        "read its ledger-held foreman handoff timeline"
    )
    assert handoff not in prompt
    assert "plan/" not in prompt


def test_supervisor_prompt_wrapup_builders_cover_ledger_and_no_epic_shapes(*, tmp_path):
    prompts = module("_supervisor_prompts")
    repo = str(tmp_path / "repo")
    topic = "alpha"
    epic = "overseer-test-epic"

    worker_wrap = prompts.wrapup_message(remaining=45, repo=repo, topic=topic, epic=epic)
    worker_wrap_no_epic = prompts.wrapup_message(remaining=20, repo=repo, topic=topic, epic=None)
    supervisor_wrap = prompts.supervisor_wrapup_message(
        remaining=45, repo=repo, topic=topic, epic=epic
    )
    supervisor_wrap_no_epic = prompts.supervisor_wrapup_message(
        remaining=20, repo=repo, topic=topic, epic=None
    )

    assert "Please start wrapping up" in worker_wrap
    assert "STOP AND WIND DOWN NOW" in worker_wrap_no_epic
    assert "NO plan epic id" in worker_wrap_no_epic
    assert "supervisor handoff entries attributed to alpha-supervisor" in supervisor_wrap
    assert "NO plan epic id" in supervisor_wrap_no_epic


def test_supervisor_prompt_nudge_builders_cover_ledger_and_no_epic_shapes(*, tmp_path):
    prompts = module("_supervisor_prompts")
    repo = str(tmp_path / "repo")
    topic = "alpha"
    epic = "overseer-test-epic"

    idle = prompts.idle_nudge_message(remaining=80, threshold=50, repo=repo, topic=topic, epic=epic)
    supervisor_idle = prompts.supervisor_idle_nudge_message(
        remaining=80, threshold=50, repo=repo, topic=topic, epic=epic
    )
    supervisor_idle_no_epic = prompts.supervisor_idle_nudge_message(
        remaining=80, threshold=50, repo=repo, topic=topic, epic=None
    )
    stall = prompts.pair_stall_nudge_message(
        repo=repo,
        topic=topic,
        epic=epic,
        worker_session="alpha",
        worker_pane="%1",
        stalled_seconds=7200.0,
    )

    assert "idle-with-context-left" in idle
    assert ".ai/supervisor-protocol.md" in supervisor_idle
    assert epic in supervisor_idle
    assert "NO plan epic id" in supervisor_idle_no_epic
    assert "2.0h" in stall
    assert "Worker plan state" in stall


def test_supervisor_pair_start_ignores_non_anchor_ledger_epic_spelling(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    plan = repo / "plan" / "alpha"
    plan.mkdir(parents=True)
    (plan / "epic.md").write_text(
        "# Plan Epic\n\n" "Ledger epic: `overseer-test-epic`\n\n",
        encoding="utf-8",
    )
    proposal = start_proposal(repo=repo, action_id="supervisor_pair_start")
    proposal["session_name"] = "alpha-supervisor"
    snapshot = proposal["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["session_identity"] = f"none:{repo}:alpha-supervisor"
    classifier = proposal["classifier"]
    assert isinstance(classifier, dict)
    start = classifier["start"]
    assert isinstance(start, dict)
    start["session_name"] = "alpha-supervisor"
    document = base_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["session_identity"] = f"none:{repo}:alpha-supervisor"
    calls: list[list[str]] = []

    result = module.act(
        proposal=proposal,
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: calls.append(argv) or 0,
    )

    assert result["reason"] == "started"
    assert "NO plan epic id" in calls[0][-1]
    assert "supervisor-handoff.md" not in calls[0][-1]
    assert "handoff.md" not in calls[0][-1]


def _resume_calls(*, repo, proposal):
    document = base_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["session_identity"] = "codex:019fc11c-68c4-78c3-824b-d9b97de55a78"
    calls: list[list[str]] = []
    result = foreman_act().act(
        proposal=proposal,
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: calls.append(argv) or 0,
    )
    assert result["outcome"] == "acted"
    assert result["mutated"] is True
    return calls


def test_resume_uses_exact_codex_session_id_and_the_ledger_epic_prompt(*, tmp_path):
    """A recorded epic gives the resumed session the SAME read-first locator the daemon's
    own restart uses — repository path and epic id, and no path into the plan tree."""
    repo = tmp_path / "repo"
    repo.mkdir()
    proposal = resume_proposal(repo=repo)
    proposal["classifier"]["resume"]["epic"] = "overseer-0007"

    calls = _resume_calls(repo=repo, proposal=proposal)

    assert calls == [
        [
            "codex",
            "resume",
            "--dangerously-bypass-approvals-and-sandbox",
            "019fc11c-68c4-78c3-824b-d9b97de55a78",
            f"resume plan epic overseer-0007 in repository {repo}; "
            "read its ledger-held plan state",
        ]
    ]


def test_resume_without_a_recorded_epic_kicks_the_restored_session_naming_no_file(*, tmp_path):
    """`codex resume <id>` restores the FULL prior conversation, so a session with no
    recorded epic gets a continuation kick rather than a pointer.

    This branch used to name `plan/<topic>/handoff.md` — a file the foreman could not
    vouch for, and which for many plans was never written at all."""
    repo = tmp_path / "repo"
    repo.mkdir()

    calls = _resume_calls(repo=repo, proposal=resume_proposal(repo=repo))

    assert calls == [
        [
            "codex",
            "resume",
            "--dangerously-bypass-approvals-and-sandbox",
            "019fc11c-68c4-78c3-824b-d9b97de55a78",
            f"continue the plan alpha work in repository {repo} from your restored session",
        ]
    ]
    assert "handoff.md" not in calls[0][-1]
    # The control: the predicate DOES report a hit on a payload of the same shape.
    assert "handoff.md" in f"{calls[0][-1]} read {repo}/plan/alpha/handoff.md and follow it"


def test_refuses_stale_unknown_freeform_and_human_actions(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    cases = [
        ({**start_proposal(repo=repo), "schema_version": 2}, "unsupported_proposal_schema"),
        ({**start_proposal(repo=repo), "action_id": "invented"}, "unknown_action"),
        ({**start_proposal(repo=repo), "command": "bd create anything"}, "free_form_command"),
        ({**start_proposal(repo=repo), "argv": ["bd", "create"]}, "free_form_command"),
        ({**start_proposal(repo=repo), "action_id": "human_valve"}, "human_action_report_only"),
        (
            {**start_proposal(repo=repo), "action_id": "blocked_session_answer"},
            "human_action_report_only",
        ),
    ]
    for proposal, reason in cases:
        result = module.act(
            proposal=proposal,
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: calls.append(argv) or 0,
        )
        assert result["outcome"] == "refused"
        assert result["mutated"] is False
        assert result["reason"] == reason

    stale_sources = {
        **base_document(repo=repo),
        "sources": {"snapshot": {"status": "ok", "mode": "list-json-observation-only"}},
    }
    stale_schema = {**base_document(repo=repo), "schema_version": 2}
    for document, reason in [
        (stale_schema, "unsupported_gather_schema"),
        (stale_sources, "snapshot_not_actable"),
    ]:
        result = module.act(
            proposal=start_proposal(repo=repo),
            gather=lambda *, repo, snapshot_path, document=document: document,
            run=lambda *, argv: calls.append(argv) or 0,
        )
        assert result["outcome"] == "refused"
        assert result["mutated"] is False
        assert result["reason"] == reason
    assert calls == []


def test_typed_work_item_filing_uses_intake_seam_and_journals_result(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    filed: list[dict[str, object]] = []
    journaled: list[dict[str, object]] = []

    result = module.act(
        proposal=file_proposal(repo=repo),
        gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
        run=lambda *, argv: 99,
        file_work_item=lambda *, request: filed.append(request) or ("overseer-new", "ready"),
        append_journal=lambda *, repo, record: journaled.append(record),
    )

    assert result == {
        "action_id": "work_item_file",
        "mutated": True,
        "outcome": "acted",
        "reason": "filed:overseer-new:ready",
    }
    assert filed == [
        {
            "target_repo": str(repo),
            "title": "File the delegated fix",
            "description": "Capture this follow-up through intake.",
            "type": "feature",
            "assignee": None,
            "depends_on": [{"kind": "local", "work_item_id": "overseer-parent"}],
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
        }
    ]
    assert journaled[-1] == {
        "stage": "foreman-act",
        "action_id": "work_item_file",
        "outcome": "acted",
        "reason": "filed:overseer-new:ready",
        "mutated": True,
    }


def test_failed_work_item_filing_returns_failed_result_and_journals_attempt(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    journaled: list[dict[str, object]] = []

    def fail_filing(*, request: dict[str, object]):
        _ = request
        msg = "filing subprocess failed because imports were unavailable"
        raise RuntimeError(msg)

    result = module.act(
        proposal=file_proposal(repo=repo),
        gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
        run=lambda *, argv: 99,
        file_work_item=fail_filing,
        append_journal=lambda *, repo, record: journaled.append(record),
    )

    assert result == {
        "action_id": "work_item_file",
        "mutated": False,
        "outcome": "failed",
        "reason": (
            "filing_subprocess_failed:" "filing subprocess failed because imports were unavailable"
        ),
    }
    assert journaled[-1] == {
        "stage": "foreman-act",
        "action_id": "work_item_file",
        "outcome": "failed",
        "reason": (
            "filing_subprocess_failed:" "filing subprocess failed because imports were unavailable"
        ),
        "mutated": False,
    }

    result = module.act(
        proposal=file_proposal(repo=repo),
        gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
        run=lambda *, argv: 99,
        file_work_item=lambda *, request: (_ for _ in ()).throw(RuntimeError("x" * 240)),
        append_journal=lambda *, repo, record: None,
    )

    assert result["outcome"] == "failed"
    assert isinstance(result["reason"], str)
    assert len(result["reason"]) == 180
    assert result["reason"].endswith("...")


def test_filing_bootstrap_resolves_configured_and_cache_plugin_roots(*, tmp_path, monkeypatch):
    module = foreman_act_filing()
    configured = tmp_path / "configured"
    cache = tmp_path / "home" / ".claude" / "plugins" / "cache"
    plugin_root = cache / "livespec-overseer" / "livespec-overseer" / "test-build"
    discovered = (
        cache
        / "livespec-orchestrator-beads-fabro"
        / "livespec-orchestrator-beads-fabro"
        / "test-build"
    )
    empty_candidate = (
        plugin_root.parent
        / "livespec-orchestrator-beads-fabro"
        / "livespec-orchestrator-beads-fabro"
    )
    empty_candidate.mkdir(parents=True)
    for root in (configured, discovered):
        (root / "scripts" / "livespec_orchestrator_beads_fabro").mkdir(parents=True)
        (root / "scripts" / "_vendor" / "livespec_runtime").mkdir(parents=True)
    (plugin_root / "overseer").mkdir(parents=True)

    monkeypatch.setenv("LIVESPEC_ORCHESTRATOR_PLUGIN_ROOT", str(configured))
    assert module._configured_orchestrator_root() == configured
    assert module._orchestrator_plugin_root() == configured
    assert module._filing_pythonpath_entries() == [
        str(configured / "scripts"),
        str(configured / "scripts" / "_vendor"),
    ]

    monkeypatch.setenv("LIVESPEC_ORCHESTRATOR_PLUGIN_ROOT", str(tmp_path / "missing"))
    assert module._configured_orchestrator_root() is None
    monkeypatch.delenv("LIVESPEC_ORCHESTRATOR_PLUGIN_ROOT")
    monkeypatch.setattr(module, "__file__", str(plugin_root / "overseer" / "foreman_act_filing.py"))
    assert module._cache_root_candidates(plugin_root=plugin_root) == [
        empty_candidate,
        cache / "livespec-orchestrator-beads-fabro" / "livespec-orchestrator-beads-fabro",
    ]
    assert module._orchestrator_plugin_root() == discovered


def test_filing_bootstrap_env_preserves_inherited_pythonpath(*, tmp_path, monkeypatch):
    module = foreman_act_filing()
    root = tmp_path / "orchestrator"
    (root / "scripts" / "livespec_orchestrator_beads_fabro").mkdir(parents=True)
    (root / "scripts" / "_vendor" / "livespec_runtime").mkdir(parents=True)

    monkeypatch.setenv("LIVESPEC_ORCHESTRATOR_PLUGIN_ROOT", str(root))
    monkeypatch.setenv("PYTHONPATH", "caller")
    env = module._filing_env()
    assert env["PYTHONPATH"] == (f"{root / 'scripts'}:{root / 'scripts' / '_vendor'}:caller")

    monkeypatch.delenv("LIVESPEC_ORCHESTRATOR_PLUGIN_ROOT")
    monkeypatch.delenv("PYTHONPATH")
    monkeypatch.setattr(module, "__file__", str(tmp_path / "overseer" / "foreman_act_filing.py"))
    assert module._orchestrator_plugin_root() is None
    assert module._filing_pythonpath_entries() == []
    assert "PYTHONPATH" not in module._filing_env()


def test_cross_repo_filing_only_files_the_target_repo(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    peer = tmp_path / "peer"
    repo.mkdir()
    peer.mkdir()
    filed: list[dict[str, object]] = []
    calls: list[list[str]] = []

    result = module.act(
        proposal=file_proposal(repo=repo, target_repo=peer),
        gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
        run=lambda *, argv: calls.append(argv) or 0,
        file_work_item=lambda *, request: filed.append(request) or ("peer-new", "pending-approval"),
        append_journal=lambda *, repo, record: None,
    )

    assert result["outcome"] == "acted"
    assert result["reason"] == "filed:peer-new:pending-approval"
    assert filed[0]["target_repo"] == str(peer)
    assert calls == []


def test_filing_refuses_malformed_or_unsafe_payloads_without_mutation(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[dict[str, object]] = []
    base = file_proposal(repo=repo)

    cases = [
        ({**base, "filing": {**base["filing"], "target_repo": "relative"}}, "malformed_filing"),
        ({**base, "filing": {**base["filing"], "title": ""}}, "malformed_filing"),
        (
            {**base, "filing": {**base["filing"], "checklist": {"single_coherent_done": True}}},
            "malformed_filing",
        ),
    ]
    for proposal, reason in cases:
        result = module.act(
            proposal=proposal,
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: 0,
            file_work_item=lambda *, request: calls.append(request) or ("bad", "ready"),
            append_journal=lambda *, repo, record: None,
        )
        assert result["outcome"] == "refused"
        assert result["reason"] == reason
        assert result["mutated"] is False
    assert calls == []


def test_dispatch_journal_reconcile_merged_is_the_only_typed_triage_command(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    dispatcher = repo / ".orchestrator" / "bin" / "dispatcher.py"
    dispatcher.parent.mkdir(parents=True)
    dispatcher.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    record = journal_record()
    calls: list[list[str]] = []

    result = module.act(
        proposal=reconcile_proposal(repo=repo, record=record),
        gather=lambda *, repo, snapshot_path: journal_document(repo=Path(repo), records=[record]),
        run=lambda *, argv: calls.append(argv) or 0,
        append_journal=lambda *, repo, record: None,
    )

    assert result == {
        "action_id": "dispatch_journal_reconcile_merged",
        "mutated": True,
        "outcome": "acted",
        "reason": "reconciled_merged_dispatch",
    }
    assert calls == [
        [
            sys.executable,
            str(dispatcher),
            "reconcile-merged",
            "--repo",
            str(repo),
            "--item",
            "overseer-a",
            "--json",
        ]
    ]


def test_dispatch_journal_triage_refuses_stale_ambiguous_or_unsupported_records(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    record = journal_record()
    other = journal_record(work_item_id="overseer-a")
    other["outcome"] = {**other["outcome"], "merge_sha": "different"}
    unsupported = {
        "stage": "dispatch-claim-abandoned",
        "work_item_id": "overseer-a",
        "status": "active",
        "reason": "no-outcome-since-ledger-admit",
    }
    calls: list[list[str]] = []

    cases = [
        (
            reconcile_proposal(repo=repo, record=record),
            journal_document(repo=repo, records=[]),
            "journal_generation_changed",
        ),
        (
            reconcile_proposal(repo=repo, record=record),
            journal_document(repo=repo, records=[record, other]),
            "ambiguous_dispatch_claim",
        ),
        (
            reconcile_proposal(repo=repo, record=unsupported),
            journal_document(repo=repo, records=[unsupported]),
            "unsupported_transition",
        ),
        (
            {
                **reconcile_proposal(repo=repo, record=record),
                "action_id": "dispatch_journal_abandon_claim",
            },
            journal_document(repo=repo, records=[record]),
            "unknown_action",
        ),
    ]
    for proposal, document, reason in cases:
        result = module.act(
            proposal=proposal,
            gather=lambda *, repo, snapshot_path, document=document: document,
            run=lambda *, argv: calls.append(argv) or 0,
            append_journal=lambda *, repo, record: None,
        )
        assert result["outcome"] == "refused"
        assert result["mutated"] is False
        assert result["reason"] == reason
    assert calls == []


def test_race_revalidates_every_identity_field_before_mutation(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    row_changed = base_document(repo=repo)
    row = row_changed["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["session_identity"] = "codex:changed"
    changed_documents = [
        ({**base_document(repo=repo), "repo": str(tmp_path / "other")}, "repo_identity_changed"),
        (
            {
                **base_document(repo=repo),
                "snapshot": {
                    **base_document(repo=repo)["snapshot"],
                    "daemon_instance_id": "daemon-2",
                },
            },
            "daemon_identity_changed",
        ),
        (base_document(repo=repo, generation=8), "tick_generation_changed"),
        (row_changed, "session_identity_changed"),
    ]
    calls: list[list[str]] = []

    for document, reason in changed_documents:
        result = module.act(
            proposal=start_proposal(repo=repo),
            gather=lambda *, repo, snapshot_path, document=document: document,
            run=lambda *, argv: calls.append(argv) or 0,
        )
        assert result["outcome"] == "refused"
        assert result["mutated"] is False
        assert result["reason"] == reason
    assert calls == []


def test_identity_token_race_coverage_is_the_existing_leg_1_contract():
    revalidate = module("foreman_act_revalidate")

    assert hasattr(revalidate, "revalidate_identity")
    assert "test_race_revalidates_every_identity_field_before_mutation" in Path(__file__).read_text(
        encoding="utf-8"
    )


def test_daemon_honors_foreman_pane_claim_by_suppressing_wrapup(*, tmp_path):
    assert PANE_CLAIM_PATH.is_file()
    pane_claim = module("foreman_pane_claim")
    builders = module("test_supervisor_builders")
    fakes = module("test_supervisor_fakes")
    registry = module("registry")

    repo, topic = builders.make_plan(tmp_path=tmp_path)
    session = registry.tmux_id(repo=str(repo), topic=topic)
    fake = fakes.FakeTmux()
    fake.serve(session=session, repo=repo, capture=builders.idle_capture(ctx=40), cmd="node")
    sup = builders.make_supervisor(tmp_path=tmp_path, fake=fake)
    pane_claim.write_pane_claim(
        repo=repo,
        topic=topic,
        claim=pane_claim.PaneClaim(
            owner="foreman",
            session=session,
            pane=session,
            runtime="claude",
            session_identity=f"none:{repo}:{topic}",
            question_fingerprint="question-1",
            acquired_at=999.0,
            expires_at=1100.0,
        ),
    )

    view = sup.evaluate(
        track=builders.mapped_track(repo=repo, topic=topic, session=session), act=True
    )

    assert view.status == "blocked:human"
    assert "foreman owns this pane" in (view.note or "")
    assert builders.wrapup_count(fake=fake) == 0


def test_blocked_answer_dismiss_and_represent_is_unreachable_until_protocol_ratified(
    *, tmp_path, monkeypatch
):
    assert PANE_CLAIM_PATH.is_file()
    module("foreman_pane_claim")
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_consensus_config(repo=repo)
    calls: list[list[str]] = []

    result = foreman_act.act(
        proposal=blocked_answer_proposal(repo=repo, mode="dismiss_and_represent"),
        gather=lambda *, repo, snapshot_path: blocked_document(repo=Path(repo)),
        run=lambda *, argv: calls.append(argv) or 0,
        consensus_panel=lambda *, request, responses: blocked_answer_panel_result(),
        append_journal=lambda *, repo, record: None,
    )

    assert result == {
        "action_id": "blocked_session_answer",
        "mutated": False,
        "outcome": "refused",
        "reason": "marker_protocol_unratified",
    }
    assert calls == []


def test_blocked_answer_existing_prompt_claims_pastes_and_cleans_up(*, tmp_path, monkeypatch):
    assert PANE_CLAIM_PATH.is_file()
    pane_claim = module("foreman_pane_claim")
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_consensus_config(repo=repo)
    proposal = blocked_answer_proposal(repo=repo)
    answer = proposal["blocked_session_answer"]
    assert isinstance(answer, dict)
    answer["question_fingerprint"] = _pane_fingerprint(text="Approve the bounded retry?\n")

    class ActTmux:
        def __init__(self):
            self.calls: list[tuple[str, str, str | None]] = []

        def pane_id(self, *, session: str):
            self.calls.append(("pane_id", session, None))
            return session

        def pane_current_command(self, *, session: str):
            self.calls.append(("cmd", session, None))
            return "node"

        def pane_current_path(self, *, session: str):
            self.calls.append(("path", session, None))
            return str(repo)

        def capture_pane(self, *, session: str):
            self.calls.append(("capture", session, None))
            return "Approve the bounded retry?\n"

        def bracketed_paste(self, *, session: str, text: str):
            assert pane_claim.active_pane_claim(
                repo=repo, topic="alpha", session=session, pane=session, now=1000.0
            )
            self.calls.append(("paste", session, text))
            return True

        def send_keys(self, *, session: str, keys: str):
            self.calls.append(("keys", session, keys))
            return True

    tmux = ActTmux()
    dispatch = module("foreman_act_dispatch")
    monkeypatch.setattr(dispatch.tmuxio, "TmuxIO", lambda: tmux)
    monkeypatch.setattr(pane_claim, "time_time", lambda: 1000.0)

    result = foreman_act.act(
        proposal=proposal,
        gather=lambda *, repo, snapshot_path: blocked_document(repo=Path(repo)),
        run=lambda *, argv: 99,
        consensus_panel=lambda *, request, responses: blocked_answer_panel_result(),
        append_journal=lambda *, repo, record: None,
    )

    assert result == {
        "action_id": "blocked_session_answer",
        "mutated": True,
        "outcome": "acted",
        "reason": "answered_existing_prompt",
    }
    assert ("paste", "alpha", "Yes, proceed with the bounded retry.") in tmux.calls
    assert ("keys", "alpha", "Enter") in tmux.calls
    assert not pane_claim.claim_path(repo=repo, topic="alpha").exists()


def test_picker_stalled_open_picker_answer_revalidates_against_fresh_capture(
    *, tmp_path, monkeypatch
):
    assert PANE_CLAIM_PATH.is_file()
    pane_claim = module("foreman_pane_claim")
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_consensus_config(repo=repo)
    question = "Approve the bounded retry?\n"
    proposal = blocked_answer_proposal(repo=repo)
    answer = proposal["blocked_session_answer"]
    assert isinstance(answer, dict)
    answer["question_fingerprint"] = _pane_fingerprint(text=question)
    document = blocked_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["status"] = "picker-stalled"
    row["picker_open"] = True
    row.pop("question_fingerprint")

    class ActTmux:
        def __init__(self):
            self.calls: list[tuple[str, str, str | None]] = []

        def pane_id(self, *, session: str):
            self.calls.append(("pane_id", session, None))
            return session

        def pane_current_command(self, *, session: str):
            self.calls.append(("cmd", session, None))
            return "node"

        def pane_current_path(self, *, session: str):
            self.calls.append(("path", session, None))
            return str(repo)

        def capture_pane(self, *, session: str):
            self.calls.append(("capture", session, None))
            return question

        def bracketed_paste(self, *, session: str, text: str):
            assert pane_claim.active_pane_claim(
                repo=repo, topic="alpha", session=session, pane=session, now=1000.0
            )
            self.calls.append(("paste", session, text))
            return True

        def send_keys(self, *, session: str, keys: str):
            self.calls.append(("keys", session, keys))
            return True

    tmux = ActTmux()
    dispatch = module("foreman_act_dispatch")
    monkeypatch.setattr(dispatch.tmuxio, "TmuxIO", lambda: tmux)
    monkeypatch.setattr(pane_claim, "time_time", lambda: 1000.0)

    result = foreman_act.act(
        proposal=proposal,
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: 99,
        consensus_panel=lambda *, request, responses: blocked_answer_panel_result(),
        append_journal=lambda *, repo, record: None,
    )

    assert result == {
        "action_id": "blocked_session_answer",
        "mutated": True,
        "outcome": "acted",
        "reason": "answered_existing_prompt",
    }
    assert ("paste", "alpha", "Yes, proceed with the bounded retry.") in tmux.calls
    assert not pane_claim.claim_path(repo=repo, topic="alpha").exists()


def test_blocked_answer_refuses_old_daemon_row_without_picker_open(*, tmp_path, monkeypatch):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_consensus_config(repo=repo)
    document = blocked_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["status"] = "picker-stalled"
    row.pop("picker_open", None)
    row.pop("question_fingerprint")

    result = foreman_act.act(
        proposal=blocked_answer_proposal(repo=repo),
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: 99,
        consensus_panel=lambda *, request, responses: blocked_answer_panel_result(),
        append_journal=lambda *, repo, record: None,
    )

    assert result == {
        "action_id": "blocked_session_answer",
        "mutated": False,
        "outcome": "refused",
        "reason": "pane_human_gate_unverified",
    }


def test_blocked_answer_refuses_fresh_capture_fingerprint_mismatch(*, tmp_path, monkeypatch):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_consensus_config(repo=repo)
    proposal = blocked_answer_proposal(repo=repo)
    answer = proposal["blocked_session_answer"]
    assert isinstance(answer, dict)
    answer["question_fingerprint"] = _pane_fingerprint(text="old question\n")
    document = blocked_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row.pop("question_fingerprint")

    class ActTmux:
        def pane_id(self, *, session: str):
            return session

        def pane_current_command(self, *, session: str):
            return "node"

        def pane_current_path(self, *, session: str):
            return str(repo)

        def capture_pane(self, *, session: str):
            return "new question\n"

    dispatch = module("foreman_act_dispatch")
    monkeypatch.setattr(dispatch.tmuxio, "TmuxIO", lambda: ActTmux())

    result = foreman_act.act(
        proposal=proposal,
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: 99,
        consensus_panel=lambda *, request, responses: blocked_answer_panel_result(),
        append_journal=lambda *, repo, record: None,
    )

    assert result == {
        "action_id": "blocked_session_answer",
        "mutated": False,
        "outcome": "refused",
        "reason": "question_fingerprint_changed_at_act_time",
    }


def test_blocked_answer_keeps_runtime_and_cwd_identity_refusals(*, tmp_path, monkeypatch):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_consensus_config(repo=repo)
    question = "Approve the bounded retry?\n"
    proposal = blocked_answer_proposal(repo=repo)
    answer = proposal["blocked_session_answer"]
    assert isinstance(answer, dict)
    answer["question_fingerprint"] = _pane_fingerprint(text=question)
    document = blocked_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row.pop("question_fingerprint")

    class ActTmux:
        def __init__(self, *, command: str | None, path: str):
            self.command = command
            self.path = path

        def pane_id(self, *, session: str):
            return session

        def pane_current_command(self, *, session: str):
            return self.command

        def pane_current_path(self, *, session: str):
            return self.path

        def capture_pane(self, *, session: str):
            return question

    dispatch = module("foreman_act_dispatch")
    cases = [
        (ActTmux(command="bash", path=str(repo)), "runtime_identity_changed"),
        (ActTmux(command="node", path=str(tmp_path)), "cwd_identity_changed"),
    ]
    for tmux, reason in cases:
        monkeypatch.setattr(dispatch.tmuxio, "TmuxIO", lambda tmux=tmux: tmux)
        result = foreman_act.act(
            proposal=proposal,
            gather=lambda *, repo, snapshot_path: document,
            run=lambda *, argv: 99,
            consensus_panel=lambda *, request, responses: blocked_answer_panel_result(),
            append_journal=lambda *, repo, record: None,
        )

        assert result == {
            "action_id": "blocked_session_answer",
            "mutated": False,
            "outcome": "refused",
            "reason": reason,
        }


def test_gate_state_restores_claude_and_codex_adapters_against_real_tmux(*, tmp_path):
    assert GATE_STATE_PATH.is_file()
    gate_state = module("foreman_gate_state")
    tmuxio = module("tmuxio")
    socket = f"gate-{os.getpid()}-{tmp_path.name}"
    wrapper = tmp_path / "tmux-private"
    wrapper.write_text(f'#!/bin/sh\nexec /usr/bin/tmux -L {socket} "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    tmux = tmuxio.TmuxIO(tmux_bin=str(wrapper))
    try:
        for runtime, text in (
            ("claude", "CLAUDE_RESTORED_SENTINEL"),
            ("codex", "CODEX_RESTORED_SENTINEL"),
        ):
            session = f"{runtime}-gate"
            subprocess.run(  # noqa: S603
                [
                    "/usr/bin/tmux",
                    "-L",
                    socket,
                    "new-session",
                    "-d",
                    "-s",
                    session,
                    "-x",
                    "80",
                    "-y",
                    "20",
                    "sh",
                    "-c",
                    "printf 'gate ready\\n'; sleep 60",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and "gate ready" not in tmux.capture_pane(
                session=session
            ):
                time.sleep(0.05)

            assert gate_state.restore_gate_state(
                tmux=tmux,
                target=session,
                state=gate_state.GateState(
                    runtime=runtime,
                    pane=session,
                    capture="gate ready\n",
                    question_text=text,
                    question_fingerprint=f"{runtime}-question",
                ),
            )
            deadline = time.monotonic() + 5.0
            capture = tmux.capture_pane(session=session)
            while time.monotonic() < deadline and text not in capture:
                time.sleep(0.05)
                capture = tmux.capture_pane(session=session)
            assert text in capture
    finally:
        subprocess.run(  # noqa: S603
            ["/usr/bin/tmux", "-L", socket, "kill-server"],
            check=False,
            capture_output=True,
            text=True,
        )


def test_cli_outputs_deterministic_json(*, tmp_path, monkeypatch, capsys):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(
        json.dumps(start_proposal(repo=repo), sort_keys=True), encoding="utf-8"
    )
    calls: list[list[str]] = []

    monkeypatch.setattr(module, "compose_document", lambda **_: base_document(repo=repo))
    monkeypatch.setattr(module, "run_command", lambda *, argv: calls.append(argv) or 0)

    assert module.main(argv=["--proposal", str(proposal_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "action_id": "plan_start",
        "mutated": True,
        "outcome": "acted",
        "reason": "started",
    }
