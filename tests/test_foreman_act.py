"""Tests for foreman_act.py — deterministic Phase B lifecycle acts."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"
MODULE_PATH = OVERSEER_DIR / "foreman_act.py"
EXECUTABLE_PATH = OVERSEER_DIR / "foreman-act"

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


def test_supervisor_pair_start_uses_exact_tmux_session_and_supervisor_handoff(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
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
            f"read {repo / 'plan' / 'alpha' / 'supervisor-handoff.md'} and follow it",
        ]
    ]


def test_resume_uses_exact_codex_session_id_and_prompt(*, tmp_path):
    module = foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    document = base_document(repo=repo)
    row = document["snapshot"]["rows"][0]
    assert isinstance(row, dict)
    row["session_identity"] = "codex:019fc11c-68c4-78c3-824b-d9b97de55a78"
    calls: list[list[str]] = []

    result = module.act(
        proposal=resume_proposal(repo=repo),
        gather=lambda *, repo, snapshot_path: document,
        run=lambda *, argv: calls.append(argv) or 0,
    )

    assert result["outcome"] == "acted"
    assert result["mutated"] is True
    assert calls == [
        [
            "codex",
            "resume",
            "--dangerously-bypass-approvals-and-sandbox",
            "019fc11c-68c4-78c3-824b-d9b97de55a78",
            f"read {repo / 'plan' / 'alpha' / 'handoff.md'} and follow it",
        ]
    ]


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
