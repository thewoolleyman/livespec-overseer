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


def test_foreman_act_module_executable_and_closed_schema_exist():
    module = foreman_act()

    assert EXECUTABLE_PATH.is_file()
    assert EXECUTABLE_PATH.stat().st_mode & 0o111
    assert module.PROPOSAL_SCHEMA_VERSION == 1
    assert module.ACTION_IDS == (
        "blocked_session_answer",
        "human_valve",
        "plan_start",
        "qualifying_session_resume",
        "qualifying_session_start",
        "supervisor_pair_start",
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
