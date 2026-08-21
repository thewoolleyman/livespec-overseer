"""Integration coverage for foreman evidence-routing scenario TODO rows."""

from __future__ import annotations

import json
from pathlib import Path

import foreman_consensus_prompt
import foreman_consensus_record
import foreman_gather_collect
import foreman_gather_render
import foreman_gather_snapshot
import foreman_runtime
import foreman_session_classifier
import pytest


def _request(*, repo: Path, question: str = "Should I run the bounded retry?"):
    return {
        "blocked_question": question,
        "repo": str(repo),
        "topic": "alpha",
        "item_id": "overseer-a7c",
        "repo_revision": "abc123",
        "item_revision": "rank:7/status:blocked",
        "handoff_or_work_item": "Implement the bounded retry.",
        "repo_context": "Python stdlib-only control-plane repo.",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 9,
            "session_identity": "codex:expected-session",
        },
    }


@pytest.mark.integration
def test_scenario_dead_track_with_conflicting_runtime_evidence_is_not_launched(*, tmp_path):
    decision = foreman_session_classifier.classify_session_lifecycle(
        coordinates=foreman_session_classifier.SessionCoordinates(
            repo=str(tmp_path), topic="alpha", session_name="alpha"
        ),
        snapshot=foreman_session_classifier.SnapshotEvidence(
            status="session-gone",
            runtime="codex",
            session_identity="codex:expected-session",
        ),
        live_sessions=[],
        indexed_sessions=[
            foreman_session_classifier.IndexedSessionEvidence(
                runtime="codex",
                repo=str(tmp_path),
                session_name="alpha",
                session_id="other-session",
                transcript_path=str(tmp_path / "transcript.jsonl"),
            )
        ],
    )

    assert decision.action == foreman_session_classifier.REPORT_ONLY
    assert decision.report is not None
    assert decision.report.reason == foreman_session_classifier.CONFLICTING_EVIDENCE
    assert decision.start is None
    assert decision.resume is None


@pytest.mark.integration
def test_scenario_foreman_reads_evidence_without_writing_session_state(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot_path = tmp_path / "missing-status.json"

    document = foreman_gather_collect.compose_document(
        repo=repo,
        snapshot_path=snapshot_path,
        list_json_command=None,
        needs_attention_command=None,
        now=lambda: "2026-08-21T00:00:00Z",
    )

    assert document["snapshot"] is None
    assert document["sources"]["snapshot"]["status"] == "skipped"
    assert not (repo / ".overseer-state").exists()
    assert not (repo / "tmp" / "overseer" / "state").exists()


@pytest.mark.integration
def test_scenario_foreman_uses_canonical_name_on_both_identity_surfaces(*, tmp_path):
    import _supervisor_foreman

    repo = tmp_path / "repo"
    repo.mkdir()
    store_path = tmp_path / "store.json"
    registered = foreman_runtime.register_foreman_track(repo=repo, store_path=store_path)
    track = _supervisor_foreman.foreman_track(repo=str(repo), store_path=store_path)

    assert registered.topic == "repo-foreman"
    assert registered.tmux == "repo-foreman"
    assert track == registered


@pytest.mark.integration
def test_scenario_foreman_relay_embeds_full_panel_record_on_first_delivery(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    request = _request(repo=repo)
    responses = {"reviewers": [{"reviewer_id": "fable", "verdict": "unblock"}]}
    verdict = {
        "outcome": "unanimous",
        "reason": None,
        "reviewers": ["fable"],
        "cache_key": "cache-1",
    }

    result = foreman_consensus_record.record_consensus_evaluation(
        request=request,
        responses=responses,
        verdict=verdict,
        cache_key="cache-1",
    )

    assert result["outcome"] == "written"
    artifact = Path(str(result["artifact"]))
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["request"] == request
    assert payload["responses"] == responses
    assert payload["verdict"] == verdict


@pytest.mark.integration
def test_scenario_escalation_quotes_session_exact_words(*, tmp_path):
    exact_question = "Approve this exact line?\nDo not paraphrase it."
    prompts = foreman_consensus_prompt.reviewer_prompts(
        request=_request(repo=tmp_path, question=exact_question)
    )

    prompt = prompts[0]["prompt"]
    assert isinstance(prompt, str)
    assert "Approve this exact line?\\nDo not paraphrase it." in prompt


@pytest.mark.integration
def test_scenario_corroboration_request_is_not_escalated_as_authority_challenge(*, tmp_path):
    prompts = foreman_consensus_prompt.reviewer_prompts(
        request=_request(repo=tmp_path, question="Which cached panel record corroborates this?")
    )

    prompt = str(prompts[0]["prompt"])
    assert "Dossier JSON:" in prompt
    assert "Escalation taxonomy" in prompt
    assert "corroborates this" in prompt
    assert "architecture" in prompt


@pytest.mark.integration
def test_scenario_unreadable_snapshot_holds_decision_context(*, tmp_path):
    snapshot_path = tmp_path / "missing.json"

    snapshot, source = foreman_gather_snapshot.read_snapshot(
        repo=tmp_path,
        snapshot_path=snapshot_path,
        list_json_command=None,
    )

    assert snapshot is None
    assert source["status"] == "skipped"
    assert "snapshot unavailable" in str(source["reason"])


@pytest.mark.integration
def test_scenario_decision_context_is_not_delivered_to_picker_parked_session(*, tmp_path):
    row = {
        "topic": "alpha",
        "repo": str(tmp_path),
        "status": "blocked:human",
        "picker_open": True,
        "stall_seconds": 120,
        "human_wait": True,
    }
    snapshot, source = foreman_gather_snapshot.snapshot_payload(
        repo=tmp_path,
        document={
            "schema_version": 1,
            "daemon_instance_id": "daemon",
            "tick_generation": 1,
            "written_at": "2026-08-21T00:00:00Z",
            "rows": [row],
        },
        mode="daemon-snapshot",
        path=None,
    )

    assert source["status"] == "ok"
    used = snapshot["rows"][0]
    assert used["picker_open"] is True
    rendered = foreman_gather_render.render_document(
        document={
            "sources": {
                "snapshot": source,
                "needs_attention": {"status": "skipped"},
                "dispatch_journal": {"status": "skipped"},
            },
            "snapshot": snapshot,
            "needs_attention": None,
            "dispatch_journal": [],
        }
    )
    assert "picker_open=yes" in rendered


@pytest.mark.integration
def test_scenario_long_lived_question_states_late_context_routing(*, tmp_path):
    question = (
        "Which option should I choose? Route later context to this standing "
        "question rather than sending an ordinary async message."
    )
    prompts = foreman_consensus_prompt.reviewer_prompts(
        request=_request(repo=tmp_path, question=question)
    )

    prompt = str(prompts[0]["prompt"])
    assert "Route later context to this standing question" in prompt
    assert "ordinary async message" in prompt
