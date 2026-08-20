"""Recovery and refusal tests for foreman work-item one-shot sessions."""

from __future__ import annotations

from pathlib import Path

from test_foreman_work_item_session_lifecycle import act_with, document, proposal

__all__: list[str] = []


def test_work_item_session_exact_crashed_resume_uses_the_recorded_handoff(*, tmp_path):
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
    resume = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_resume",
            classifier_action="exact_resume",
        ),
        calls=calls,
    )

    assert start["outcome"] == "acted"
    assert resume["reason"] == "work_item_session_resumed"
    assert calls[1][:4] == [
        "codex",
        "resume",
        "--dangerously-bypass-approvals-and-sandbox",
        "019fc11c-68c4-78c3-824b-d9b97de55a78",
    ]
    assert "tmp/overseer/foreman/work-items/overseer-vts4lo/handoff.md" in calls[1][-1]


def test_work_item_session_refuses_duplicate_phantom_claim(*, tmp_path):
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
    duplicate = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo, action_id="work_item_session_start", classifier_action="start"
        ),
    )

    assert duplicate["outcome"] == "refused"
    assert duplicate["reason"] == "work_item_claim_active"


def test_work_item_session_missing_handoff_and_ambiguous_classifier_are_report_only(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []
    missing_payload = proposal(
        repo=repo, action_id="work_item_session_start", classifier_action="start"
    )
    work_item = missing_payload["work_item_session"]
    assert isinstance(work_item, dict)
    work_item["handoff"] = ""

    missing_handoff = act_with(repo=repo, proposal_payload=missing_payload, calls=calls)
    ambiguous = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_start",
            classifier_action="report_only",
        ),
        calls=calls,
    )

    assert missing_handoff["reason"] == "missing_handoff"
    assert ambiguous["reason"] == "classifier_report_only"
    assert calls == []


def test_work_item_session_refuses_missing_work_item_evidence(*, tmp_path):
    module_payload = proposal(
        repo=tmp_path / "repo",
        action_id="work_item_session_start",
        classifier_action="start",
    )
    module = __import__("test_foreman_work_item_session_lifecycle").foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()

    result = module.act(
        proposal=module_payload,
        seams=module.ActSeams(
            gather=lambda *, repo, snapshot_path: {
                **document(repo=Path(repo)),
                "needs_attention": {"items": []},
            },
            run=lambda *, argv: 0,
            append_journal=lambda *, repo, record: None,
        ),
    )

    assert result["outcome"] == "refused"
    assert result["reason"] == "work_item_evidence_missing"


def test_work_item_session_revalidates_snapshot_and_identity_edges(*, tmp_path):
    module = __import__("test_foreman_work_item_session_lifecycle").foreman_act()
    repo = tmp_path / "repo"
    repo.mkdir()
    base = proposal(repo=repo, action_id="work_item_session_start", classifier_action="start")
    changed_doc = document(repo=repo)
    changed_snapshot = changed_doc["snapshot"]
    assert isinstance(changed_snapshot, dict)

    cases = [
        ({**changed_doc, "repo": str(tmp_path / "other")}, base, "repo_identity_changed"),
        (
            {**changed_doc, "snapshot": {**changed_snapshot, "daemon_instance_id": "daemon-2"}},
            base,
            "daemon_identity_changed",
        ),
        (
            {**changed_doc, "snapshot": {**changed_snapshot, "tick_generation": 8}},
            base,
            "tick_generation_changed",
        ),
        (
            changed_doc,
            {key: value for key, value in base.items() if key != "work_item_session"},
            "malformed_work_item_session",
        ),
        (
            changed_doc,
            {**base, "work_item_session": {**base["work_item_session"], "session_name": "other"}},
            "work_item_identity_changed",
        ),
    ]

    for current_doc, current_proposal, reason in cases:
        result = module.act(
            proposal=current_proposal,
            seams=module.ActSeams(
                gather=lambda *, repo, snapshot_path, current_doc=current_doc: current_doc,
                run=lambda *, argv: 0,
                append_journal=lambda *, repo, record: None,
            ),
        )
        assert result["outcome"] == "refused"
        assert result["reason"] == reason


def test_work_item_session_resume_and_finish_refuse_incomplete_evidence(*, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    calls: list[list[str]] = []

    bad_resume = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_resume",
            classifier_action="report_only",
        ),
        calls=calls,
    )
    missing_handoff = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_resume",
            classifier_action="exact_resume",
        ),
        calls=calls,
    )
    missing_terminal = act_with(
        repo=repo,
        proposal_payload=proposal(
            repo=repo,
            action_id="work_item_session_finish",
            classifier_action="report_only",
            terminal_status="completed",
        ),
        calls=calls,
    )
    assert (
        act_with(
            repo=repo,
            proposal_payload=proposal(
                repo=repo, action_id="work_item_session_start", classifier_action="start"
            ),
        )["outcome"]
        == "acted"
    )
    missing_resume_object = proposal(
        repo=repo,
        action_id="work_item_session_resume",
        classifier_action="exact_resume",
    )
    classifier = missing_resume_object["classifier"]
    assert isinstance(classifier, dict)
    del classifier["resume"]
    classifier_mismatch = act_with(repo=repo, proposal_payload=missing_resume_object, calls=calls)

    assert bad_resume["reason"] == "classifier_report_only"
    assert missing_handoff["reason"] == "missing_handoff"
    assert classifier_mismatch["reason"] == "classifier_mismatch"
    assert missing_terminal["reason"] == "missing_handoff"
    assert calls == []
