"""Integration coverage for the ratified foreman valve-disposition policy."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

OVERSEER_DIR = Path(__file__).resolve().parents[2] / "overseer"
POLICY_PATH = OVERSEER_DIR / "foreman_valve_policy.py"

__all__: list[str] = []


def module(name: str):
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module(name)


def write_config(*, repo: Path, value: object, include_key: bool = True) -> None:
    repo.mkdir()
    payload: dict[str, object] = {"livespec-overseer": {}}
    section = payload["livespec-overseer"]
    assert isinstance(section, dict)
    if include_key:
        section["foreman_valve_disposition"] = value
    (repo / ".livespec.jsonc").write_text(json.dumps(payload), encoding="utf-8")


def base_document(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {"snapshot": {"status": "ok", "mode": "daemon-snapshot"}},
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
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


def valve_proposal(*, repo: Path, action_id: str = "human_valve") -> dict[str, object]:
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
        "human_valve": {"category": "ordinary"},
        "consensus": {
            "request": {"item_id": "overseer-ym6", "choice": "start alpha"},
            "reviewer_responses": {},
        },
    }


def unanimous_panel_result() -> dict[str, object]:
    reviewers = [
        {
            "reviewer_id": "fable",
            "model": {
                "reviewer_id": "fable",
                "vendor": "anthropic",
                "model": "claude-fable-5",
            },
            "verdict": "unblock",
            "action": {"action_id": "plan_start", "params": {}},
        },
        {
            "reviewer_id": "opus",
            "model": {
                "reviewer_id": "opus",
                "vendor": "anthropic",
                "model": "claude-opus-5",
            },
            "verdict": "unblock",
            "action": {"action_id": "plan_start", "params": {}},
        },
        {
            "reviewer_id": "gpt-sol",
            "model": {
                "reviewer_id": "gpt-sol",
                "vendor": "openai",
                "model": "gpt-5.6-sol",
            },
            "verdict": "unblock",
            "action": {"action_id": "plan_start", "params": {}},
        },
    ]
    return {
        "schema_version": 1,
        "outcome": "unanimous",
        "reason": "three_typed_actions_equal",
        "action": {"action_id": "plan_start", "params": {}},
        "reviewers": reviewers,
        "models": [reviewer["model"] for reviewer in reviewers],
        "cache_key": "abc123",
        "mutated": False,
    }


def test_effective_valve_disposition_is_readable_and_fails_closed(*, tmp_path, capsys):
    assert POLICY_PATH.is_file()
    policy = module("foreman_valve_policy")
    absent = tmp_path / "absent"
    absent.mkdir()
    wrong_type = tmp_path / "wrong-type"
    unknown = tmp_path / "unknown"
    consensus = tmp_path / "consensus"
    write_config(repo=wrong_type, value=["consensus"])
    write_config(repo=unknown, value="delegated")
    write_config(repo=consensus, value="consensus")

    assert policy.effective_valve_disposition(repo=absent) == {
        "configured": None,
        "effective": "report-only",
        "recognized": True,
        "source": "default",
    }
    assert policy.effective_valve_disposition(repo=wrong_type)["effective"] == "report-only"
    assert policy.effective_valve_disposition(repo=unknown) == {
        "configured": "delegated",
        "effective": "report-only",
        "recognized": False,
        "source": str(unknown / ".livespec.jsonc"),
        "warning": "unrecognized_foreman_valve_disposition",
    }
    assert policy.effective_valve_disposition(repo=consensus)["effective"] == "consensus"
    assert policy.main(argv=["--repo", str(consensus)]) == 0
    assert json.loads(capsys.readouterr().out)["effective"] == "consensus"


def test_absent_config_keeps_human_valves_report_only_byte_identical(*, tmp_path):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    result = foreman_act.act(
        proposal=valve_proposal(repo=repo),
        seams=foreman_act.ActSeams(
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: calls.append(argv) or 0,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result == {
        "action_id": "human_valve",
        "mutated": False,
        "outcome": "refused",
        "reason": "human_action_report_only",
    }
    assert calls == []


def test_blocked_session_answer_consensus_refusals_keep_requested_action_id(*, tmp_path):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    result = foreman_act.act(
        proposal=valve_proposal(repo=repo, action_id="blocked_session_answer"),
        seams=foreman_act.ActSeams(
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: calls.append(argv) or 0,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result == {
        "action_id": "blocked_session_answer",
        "mutated": False,
        "outcome": "refused",
        "reason": "human_action_report_only",
    }
    assert calls == []


def test_consensus_disposition_journals_before_acting(*, tmp_path):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    write_config(repo=repo, value="consensus")
    events: list[str] = []
    journaled: list[dict[str, object]] = []

    result = foreman_act.act(
        proposal=valve_proposal(repo=repo),
        seams=foreman_act.ActSeams(
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: events.append("run") or 0,
            consensus_panel=lambda *, request, responses: unanimous_panel_result(),
            append_journal=lambda *, repo, record: events.append("journal")
            or journaled.append(record),
        ),
    )

    assert result == {
        "action_id": "plan_start",
        "mutated": True,
        "outcome": "acted",
        "reason": "started",
    }
    assert events[:2] == ["journal", "run"]
    assert journaled[0]["stage"] == "foreman-consensus-act"
    assert journaled[0]["governing_setting"] == "foreman_valve_disposition=consensus"
    assert journaled[0]["panel_outcome"] == "unanimous"
    assert journaled[0]["authorized_action_id"] == "plan_start"
    assert len(journaled[0]["reviewers"]) == 3


def test_blocked_session_answer_consensus_audit_records_requested_action_id(*, tmp_path):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    write_config(repo=repo, value="consensus")
    journaled: list[dict[str, object]] = []

    result = foreman_act.act(
        proposal=valve_proposal(repo=repo, action_id="blocked_session_answer"),
        seams=foreman_act.ActSeams(
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: 0,
            consensus_panel=lambda *, request, responses: unanimous_panel_result(),
            append_journal=lambda *, repo, record: journaled.append(record),
        ),
    )

    assert result["outcome"] == "acted"
    assert journaled[0]["stage"] == "foreman-consensus-act"
    assert journaled[0]["action_id"] == "blocked_session_answer"
    assert journaled[0]["authorized_action_id"] == "plan_start"


def test_consensus_floors_and_missing_evidence_escalate_without_mutation(*, tmp_path):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    write_config(repo=repo, value="consensus")
    calls: list[list[str]] = []

    hard_floor = valve_proposal(repo=repo)
    hard_floor["human_valve"] = {"category": "human-gated-by-design"}
    missing_evidence = valve_proposal(repo=repo)
    del missing_evidence["consensus"]

    for proposal, reason in [
        (hard_floor, "hard_floor:human-gated-by-design"),
        (missing_evidence, "consensus_evidence_unavailable"),
    ]:
        result = foreman_act.act(
            proposal=proposal,
            seams=foreman_act.ActSeams(
                gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
                run=lambda *, argv: calls.append(argv) or 0,
                append_journal=lambda *, repo, record: None,
            ),
        )
        assert result["outcome"] == "refused"
        assert result["mutated"] is False
        assert result["reason"] == reason
    assert calls == []


def test_consensus_refuses_silent_auto_disposition_when_journal_fails(*, tmp_path):
    foreman_act = module("foreman_act")
    repo = tmp_path / "repo"
    write_config(repo=repo, value="consensus")
    calls: list[list[str]] = []

    def fail_append(*, repo: Path, record: dict[str, object]) -> None:
        _ = (repo, record)
        raise OSError("journal unavailable")

    result = foreman_act.act(
        proposal=valve_proposal(repo=repo),
        seams=foreman_act.ActSeams(
            gather=lambda *, repo, snapshot_path: base_document(repo=Path(repo)),
            run=lambda *, argv: calls.append(argv) or 0,
            consensus_panel=lambda *, request, responses: unanimous_panel_result(),
            append_journal=fail_append,
        ),
    )

    assert result == {
        "action_id": "human_valve",
        "mutated": False,
        "outcome": "refused",
        "reason": "journal_append_failed",
    }
    assert calls == []
