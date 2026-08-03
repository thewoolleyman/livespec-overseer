"""Tests for bounded foreman work-item one-shot sessions."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

__all__: list[str] = []

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"


def foreman_act():
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module("foreman_act")


def document(*, repo: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repo": str(repo),
        "sources": {
            "snapshot": {"status": "ok", "mode": "daemon-snapshot"},
            "dispatch_journal": {"status": "ok", "records_read": 1},
        },
        "snapshot": {"daemon_instance_id": "daemon-1", "tick_generation": 7, "rows": []},
        "needs_attention": {"items": [{"id": "overseer-vts4lo", "kind": "work-item"}]},
        "dispatch_journal": [],
    }


def proposal(
    *,
    repo: Path,
    action_id: str,
    classifier_action: str,
    terminal_status: str | None = None,
) -> dict[str, object]:
    work_item_id = "overseer-vts4lo"
    payload: dict[str, object] = {
        "work_item_id": work_item_id,
        "session_name": work_item_id,
        "handoff": "durable handoff\n",
    }
    if terminal_status is not None:
        payload["terminal"] = {"status": terminal_status, "reason": "measured terminal state"}
    classifier: dict[str, object] = {"action": classifier_action}
    if classifier_action == "start":
        classifier["start"] = {
            "repo": str(repo),
            "topic": work_item_id,
            "session_name": work_item_id,
        }
    if classifier_action == "exact_resume":
        classifier["resume"] = {
            "runtime": "codex",
            "repo": str(repo),
            "topic": work_item_id,
            "session_name": work_item_id,
            "session_id": "019fc11c-68c4-78c3-824b-d9b97de55a78",
            "transcript_path": "/home/me/.codex/sessions/rollout.jsonl",
        }
    return {
        "schema_version": 1,
        "action_id": action_id,
        "repo": str(repo),
        "topic": work_item_id,
        "session_name": work_item_id,
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 7,
            "session_identity": None,
        },
        "classifier": classifier,
        "work_item_session": payload,
    }


def state_dir(*, repo: Path) -> Path:
    return repo / "tmp" / "overseer" / "foreman" / "work-items" / "overseer-vts4lo"


def read_json(*, path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def act_with(
    *,
    repo: Path,
    proposal_payload: dict[str, object],
    calls: list[list[str]] | None = None,
) -> dict[str, object]:
    module = foreman_act()
    return module.act(
        proposal=proposal_payload,
        gather=lambda *, repo, snapshot_path: document(repo=Path(repo)),
        run=lambda *, argv: (calls.append(argv) if calls is not None else None) or 0,
        append_journal=lambda *, repo, record: None,
    )


def test_work_item_session_create_to_terminal_cleanup_preserves_outcome(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    start = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo, action_id="work_item_session_start", classifier_action="start"
        ),
        calls=calls,
    )
    finish = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_finish",
            classifier_action="report_only",
            terminal_status="completed",
        ),
        calls=calls,
    )

    assert start["reason"] == "work_item_session_started"
    assert finish["reason"] == "work_item_session_completed"
    assert not (state_dir(repo=repo) / "claim.json").exists()
    assert read_json(path=state_dir(repo=repo) / "outcome.json")["status"] == "completed"
    assert read_json(path=state_dir(repo=repo) / "handoff.json")["work_item_id"] == (
        "overseer-vts4lo"
    )


def test_work_item_session_resume_refreshes_the_durable_handoff(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []
    start = proposal(repo=repo, action_id="work_item_session_start", classifier_action="start")
    resume = proposal(
        repo=repo,
        action_id="work_item_session_resume",
        classifier_action="exact_resume",
    )
    work_item = resume["work_item_session"]
    assert isinstance(work_item, dict)
    work_item["handoff"] = "fresh resume handoff\n"

    assert act_with(repo=repo, proposal_payload=start, calls=calls)["outcome"] == "acted"
    result = act_with(repo=repo, proposal_payload=resume, calls=calls)

    handoff = state_dir(repo=repo) / "handoff.md"
    assert result["reason"] == "work_item_session_resumed"
    assert handoff.read_text(encoding="utf-8") == "fresh resume handoff\n"
    assert str(handoff) in " ".join(calls[-1])


def test_work_item_session_retry_after_journaled_terminal_failure(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo, action_id="work_item_session_start", classifier_action="start"
            ),
        )["outcome"]
        == "acted"
    )
    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo,
                action_id="work_item_session_finish",
                classifier_action="report_only",
                terminal_status="failed",
            ),
        )["reason"]
        == "work_item_session_failed"
    )

    retry = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo, action_id="work_item_session_start", classifier_action="start"
        ),
    )

    assert retry["reason"] == "work_item_session_started"
    assert read_json(path=state_dir(repo=repo) / "claim.json")["attempt"] == 2


def test_work_item_session_queued_run_eviction_records_cleanup_evidence(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo, action_id="work_item_session_start", classifier_action="start"
            ),
        )["outcome"]
        == "acted"
    )
    eviction = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_finish",
            classifier_action="report_only",
            terminal_status="evicted",
        ),
    )

    outcome = read_json(path=state_dir(repo=repo) / "outcome.json")
    assert eviction["reason"] == "work_item_session_evicted"
    assert outcome["status"] == "evicted"
    assert not Path(str(outcome["claim_path"])).exists()
