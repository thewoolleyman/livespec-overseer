"""Integration coverage for full-autonomy consensus majority rules."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import foreman_act_consensus
import foreman_consensus
import foreman_consensus_prompt
import pytest

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "foreman-consensus"
    / "recorded-picker-reviewer-responses.json"
)


def _request(*, repo: Path, question: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "blocked_question": question,
        "repo": str(repo),
        "topic": "alpha",
        "item_id": "overseer-3h4s5w.3",
        "repo_revision": "abc123",
        "item_revision": "rank:7/status:ready",
        "handoff_or_work_item": "Use the recorded picker panel as the production seed.",
        "repo_context": "Python stdlib-only control-plane repo.",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 9,
            "session_identity": "codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
        },
    }


def _write_config(*, repo: Path, full_autonomy: bool) -> None:
    section: dict[str, object] = {"foreman_valve_disposition": "consensus"}
    if full_autonomy:
        section["full_autonomy"] = True
    (repo / ".livespec.jsonc").write_text(
        json.dumps({"livespec-overseer": section}), encoding="utf-8"
    )


def _fixture_payload() -> dict[str, object]:
    loaded = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _panel(*, payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload["reviewers"]
    assert isinstance(raw, list)
    panel = [reviewer for reviewer in raw if isinstance(reviewer, dict)]
    assert len(panel) == 3
    return panel


def _action(*, action_id: str, target: str) -> dict[str, object]:
    return {"action_id": action_id, "params": {"target": target}}


def _set_picker_answers(*, payload: dict[str, object], answers: tuple[str, str, str]) -> None:
    for reviewer, answer in zip(_panel(payload=payload), answers, strict=True):
        action = reviewer["action"]
        assert isinstance(action, dict)
        params = action["params"]
        assert isinstance(params, dict)
        params["answer"] = answer


def _set_actions(
    *,
    payload: dict[str, object],
    actions: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    for reviewer, action in zip(_panel(payload=payload), actions, strict=True):
        reviewer["action"] = copy.deepcopy(action)


def _result(
    *, tmp_path: Path, repo: Path, responses: dict[str, object], question: str
) -> dict[str, object]:
    return foreman_consensus.consensus(
        request=_request(repo=repo, question=question),
        responses=responses,
        state_dir=tmp_path / question.replace(" ", "-"),
    )


def _majority_repo(*, tmp_path: Path) -> Path:
    repo = tmp_path / "majority-repo"
    repo.mkdir()
    _write_config(repo=repo, full_autonomy=True)
    return repo


def _unanimous_repo(*, tmp_path: Path) -> Path:
    repo = tmp_path / "unanimous-repo"
    repo.mkdir()
    _write_config(repo=repo, full_autonomy=False)
    return repo


@pytest.mark.integration
def test_scenario_strict_majority_authorizes_action_under_full_autonomy(*, tmp_path: Path):
    repo = _majority_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    _set_picker_answers(payload=payload, answers=("3", "1", "1"))

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="majority picker")

    assert result["outcome"] == "majority"
    assert result["outcome"] != "unanimous"
    assert result["decision_rule"] == "majority"
    assert result["action"]["action_id"] == "blocked_session_answer"
    assert result["action"]["params"]["answer"] == "1"


@pytest.mark.integration
def test_majority_rule_still_escalates_one_one_one_split(*, tmp_path: Path):
    repo = _majority_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    _set_picker_answers(payload=payload, answers=("1", "2", "4"))

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="one one one")

    assert result["outcome"] == "escalate"
    assert result["reason"] == "typed_action_disagreement"
    assert result["decision_rule"] == "majority"


@pytest.mark.integration
def test_unanimous_rule_preserves_minority_override(*, tmp_path: Path):
    repo = _unanimous_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    panel = _panel(payload=payload)
    panel[0]["verdict"] = "needs-human"
    panel[0]["action"] = {"action_id": "human_valve", "params": {"reason": "architecture"}}
    for reviewer in panel[1:]:
        action = reviewer["action"]
        assert isinstance(action, dict)
        action["reversible"] = True
        action["rollback"] = {"bounded": True}
    payload["minority_report_round"] = {
        "holders": [
            {"reviewer_id": "opus", "holds": True},
            {"reviewer_id": "gpt-sol", "holds": True},
        ],
    }

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="minority held")

    assert result["outcome"] == "minority_override"
    assert result["reason"] == "minority_report_both_holders_confirmed"
    assert result["decision_rule"] == "unanimous"


@pytest.mark.integration
def test_scenario_security_dissent_escalates_under_majority_rule(*, tmp_path: Path):
    repo = _majority_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    panel = _panel(payload=payload)
    panel[2]["verdict"] = "needs-human"
    panel[2]["hard_risk"] = True
    panel[2]["risk_kind"] = "security"
    panel[2]["action"] = {"action_id": "human_valve", "params": {"reason": "security"}}

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="security")

    assert result["outcome"] == "escalate"
    assert result["reason"] == "security_dissent"
    assert result["decision_rule"] == "majority"


@pytest.mark.integration
def test_scenario_same_split_escalates_under_unanimous_decision_rule(*, tmp_path: Path):
    repo = _unanimous_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    _set_picker_answers(payload=payload, answers=("3", "1", "1"))

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="unanimous split")

    assert result["outcome"] == "escalate"
    assert result["reason"] == "typed_action_disagreement"
    assert result["decision_rule"] == "unanimous"


@pytest.mark.integration
def test_scenario_insufficient_information_abstains_under_majority_rule(*, tmp_path: Path):
    majority_repo = _majority_repo(tmp_path=tmp_path)
    unanimous_repo = _unanimous_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    _panel(payload=payload)[0]["verdict"] = "insufficient-information"

    majority = _result(
        tmp_path=tmp_path, repo=majority_repo, responses=payload, question="abstain majority"
    )
    unanimous = _result(
        tmp_path=tmp_path,
        repo=unanimous_repo,
        responses=payload,
        question="abstain unanimous",
    )

    assert majority["outcome"] == "majority"
    assert majority["decision_rule"] == "majority"
    assert majority["action"]["params"]["answer"] == "1"
    assert unanimous["outcome"] == "escalate"
    assert unanimous["reason"] == "insufficient_information"
    assert unanimous["decision_rule"] == "unanimous"


@pytest.mark.integration
def test_scenario_other_hard_risk_dissent_is_outvoted_under_majority_rule(*, tmp_path: Path):
    repo = _majority_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    panel = _panel(payload=payload)
    panel[2]["verdict"] = "needs-human"
    panel[2]["hard_risk"] = True
    panel[2]["risk_kind"] = "other"
    panel[2]["action"] = {"action_id": "human_valve", "params": {"reason": "architecture"}}

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="other risk")

    assert result["outcome"] == "majority"
    assert result["decision_rule"] == "majority"
    assert result["dissent"]["reviewer_id"] == "gpt-sol"
    assert result["action"]["params"]["answer"] == "1"


@pytest.mark.integration
def test_majority_rule_authorizes_typed_ruling_majority(*, tmp_path: Path):
    repo = _majority_repo(tmp_path=tmp_path)
    payload = _fixture_payload()
    _set_actions(
        payload=payload,
        actions=(
            _action(action_id="plan_start", target="alpha"),
            _action(action_id="work_item_file", target="overseer-next"),
            _action(action_id="work_item_file", target="overseer-next"),
        ),
    )

    result = _result(tmp_path=tmp_path, repo=repo, responses=payload, question="typed ruling")

    assert result["outcome"] == "majority"
    assert result["decision_rule"] == "majority"
    assert result["action"] == _action(action_id="work_item_file", target="overseer-next")


@pytest.mark.integration
def test_actuator_refuses_majority_verdict_when_effective_rule_is_unanimous(*, tmp_path: Path):
    majority_repo = _majority_repo(tmp_path=tmp_path)
    unanimous_repo = _unanimous_repo(tmp_path=tmp_path)
    responses = _fixture_payload()
    _set_picker_answers(payload=responses, answers=("3", "1", "1"))
    request = _request(repo=majority_repo, question="act time mismatch")
    verdict = foreman_consensus.consensus(
        request=request,
        responses=responses,
        state_dir=tmp_path / "act-time-majority-source",
    )
    assert verdict["outcome"] == "majority"

    action, refusal = foreman_act_consensus.prepare_consensus_action(
        action_id="blocked_session_answer",
        proposal={
            "repo": str(unanimous_repo),
            "topic": "alpha",
            "consensus": {"request": request, "reviewer_responses": responses},
        },
        disposition={
            "effective": "consensus",
            "full_autonomy": False,
            "decision_rule": "unanimous",
        },
        consensus_panel=lambda *, request, responses: verdict,
        append_journal=lambda *, repo, record: None,
    )

    assert action is None
    assert refusal == {
        "action_id": "blocked_session_answer",
        "mutated": False,
        "outcome": "refused",
        "reason": "consensus_majority_requires_majority_rule",
    }


@pytest.mark.integration
def test_reviewer_prompt_requests_hard_risk_kind(*, tmp_path: Path):
    prompt = foreman_consensus_prompt.reviewer_prompt(
        request=_request(repo=tmp_path, question="prompt risk kind"),
        identity={"reviewer_id": "fable", "vendor": "anthropic", "model": "claude-fable-5"},
    )["prompt"]

    assert isinstance(prompt, str)
    assert "risk_kind" in prompt
    assert "security" in prompt
    assert "other" in prompt
