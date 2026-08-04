"""In-process coverage for the Phase C report-only consensus panel."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

OVERSEER_DIR = Path(__file__).resolve().parents[1] / "overseer"

__all__: list[str] = []


def module(name: str):
    if str(OVERSEER_DIR) not in sys.path:
        sys.path.insert(0, str(OVERSEER_DIR))
    return importlib.import_module(name)


def request(*, repo: Path, question: str = "Should I run the formatter now?") -> dict[str, object]:
    return {
        "schema_version": 1,
        "blocked_question": question,
        "repo": str(repo),
        "topic": "alpha",
        "item_id": "overseer-a7c",
        "repo_revision": "abc123",
        "item_revision": "rank:7/status:blocked",
        "handoff_or_work_item": "Implement the bounded formatter step.",
        "repo_context": "Python stdlib-only control-plane repo.",
        "snapshot": {
            "daemon_instance_id": "daemon-1",
            "tick_generation": 9,
            "session_identity": "codex:019fc11c-68c4-78c3-824b-d9b97de55a78",
        },
    }


def reviewers(*, action: object | None = None) -> dict[str, object]:
    typed = action or {"action_id": "work_item_file", "params": {"target": "overseer-next"}}
    return {
        "reviewers": [
            {"reviewer_id": "fable", "verdict": "unblock", "action": typed},
            {"reviewer_id": "opus", "verdict": "unblock", "action": typed},
            {"reviewer_id": "gpt-sol", "verdict": "unblock", "action": typed},
        ]
    }


def test_model_identities_are_verified_seed_panel_and_fail_loudly():
    types = module("foreman_consensus_types")

    assert types.MODEL_IDENTITIES == (
        {
            "reviewer_id": "fable",
            "vendor": "anthropic",
            "model": "claude-fable-5",
        },
        {
            "reviewer_id": "opus",
            "vendor": "anthropic",
            "model": "claude-opus-5",
        },
        {
            "reviewer_id": "gpt-sol",
            "vendor": "openai",
            "model": "gpt-5.6-sol",
        },
    )

    with pytest.raises(
        ValueError,
        match=(
            "^unresolvable pinned model identity for reviewer fable: "
            "anthropic/claude-fable-5-20260804$"
        ),
    ):
        types.construct_model_identities(
            identities=(
                {
                    "reviewer_id": "fable",
                    "vendor": "anthropic",
                    "model": "claude-fable-5-20260804",
                },
                {
                    "reviewer_id": "opus",
                    "vendor": "anthropic",
                    "model": "claude-opus-5",
                },
                {
                    "reviewer_id": "gpt-sol",
                    "vendor": "openai",
                    "model": "gpt-5.6-sol",
                },
            )
        )

    with pytest.raises(
        ValueError,
        match="^duplicate resolved model identity: anthropic/claude-fable-5$",
    ):
        types.construct_model_identities(
            identities=(
                {
                    "reviewer_id": "fable",
                    "vendor": "anthropic",
                    "model": "claude-fable-5",
                },
                {
                    "reviewer_id": "opus",
                    "vendor": "anthropic",
                    "model": "claude-fable-5",
                },
                {
                    "reviewer_id": "gpt-sol",
                    "vendor": "openai",
                    "model": "gpt-5.6-sol",
                },
            )
        )

    with pytest.raises(
        ValueError,
        match="^consensus panel must have exactly one non-Anthropic reviewer$",
    ):
        types.construct_model_identities(
            identities=(
                {
                    "reviewer_id": "fable",
                    "vendor": "anthropic",
                    "model": "claude-fable-5",
                },
                {
                    "reviewer_id": "opus",
                    "vendor": "anthropic",
                    "model": "claude-opus-5",
                },
                {
                    "reviewer_id": "sonnet",
                    "vendor": "anthropic",
                    "model": "claude-sonnet-5",
                },
            )
        )

    non_anthropic = [
        identity for identity in types.MODEL_IDENTITIES if identity["vendor"] != "anthropic"
    ]
    assert [identity["reviewer_id"] for identity in non_anthropic] == ["gpt-sol"]


def test_consensus_module_executable_schema_and_typed_unanimity(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()

    assert (OVERSEER_DIR / "foreman-consensus").is_file()
    assert (OVERSEER_DIR / "foreman-consensus").stat().st_mode & 0o111
    assert consensus.PANEL_SCHEMA_VERSION == 1

    result = consensus.consensus(
        request=request(repo=repo),
        responses=reviewers(),
        state_dir=tmp_path / "state",
    )

    assert result["outcome"] == "unanimous"
    assert result["reason"] == "three_typed_actions_equal"
    assert result["action"] == {
        "action_id": "work_item_file",
        "params": {"target": "overseer-next"},
    }
    assert result["mutated"] is False
    assert result["cache"] == "miss"

    cached = consensus.consensus(
        request=request(repo=repo),
        responses=reviewers(action="this ignored response would otherwise escalate"),
        state_dir=tmp_path / "state",
    )

    assert cached["outcome"] == "unanimous"
    assert cached["cache"] == "hit"


def test_free_form_invalid_actions_and_typed_disagreement_escalate(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()

    cases = [
        ("free_form_action", "continue with prose"),
        ("free_form_action", {"action_id": "work_item_file", "params": []}),
        ("free_form_action", {"action_id": "invented", "params": {}}),
    ]
    for index, (reason, action) in enumerate(cases):
        result = consensus.consensus(
            request=request(repo=repo, question=f"bad action {index}"),
            responses=reviewers(action=action),
            state_dir=tmp_path / f"state-{index}",
        )
        assert result["outcome"] == "escalate"
        assert result["reason"] == reason
        assert result["action"] == {"action_id": "human_valve", "params": {}}

    split = reviewers()
    panel = split["reviewers"]
    assert isinstance(panel, list)
    last = panel[2]
    assert isinstance(last, dict)
    last["action"] = {"action_id": "plan_start", "params": {"target": "overseer-next"}}

    disagreement = consensus.consensus(
        request=request(repo=repo, question="typed but different"),
        responses=split,
        state_dir=tmp_path / "state-disagreement",
    )
    assert disagreement["outcome"] == "escalate"
    assert disagreement["reason"] == "typed_action_disagreement"


def test_needs_human_escalates_and_non_anthropic_dissent_is_non_overridable(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()

    anthro = reviewers()
    anthro_panel = anthro["reviewers"]
    assert isinstance(anthro_panel, list)
    fable = anthro_panel[0]
    assert isinstance(fable, dict)
    fable["verdict"] = "needs-human"
    fable["action"] = {"action_id": "human_valve", "params": {"reason": "architecture"}}

    anthro_result = consensus.consensus(
        request=request(repo=repo),
        responses=anthro,
        state_dir=tmp_path / "state-anthro",
    )
    assert anthro_result["outcome"] == "escalate"
    assert anthro_result["reason"] == "needs_human"

    non_anthro = reviewers()
    non_anthro_panel = non_anthro["reviewers"]
    assert isinstance(non_anthro_panel, list)
    gpt_sol = non_anthro_panel[2]
    assert isinstance(gpt_sol, dict)
    gpt_sol["verdict"] = "needs-human"
    gpt_sol["action"] = {"action_id": "human_valve", "params": {"reason": "architecture"}}

    non_anthro_result = consensus.consensus(
        request=request(repo=repo, question="non anthro dissent"),
        responses=non_anthro,
        state_dir=tmp_path / "state-non-anthro",
    )
    assert non_anthro_result["outcome"] == "escalate"
    assert non_anthro_result["reason"] == "non_anthropic_needs_human_dissent"
    assert non_anthro_result["dissent"]["reviewer_id"] == "gpt-sol"


def test_minority_report_override_is_reachable_with_seed_panel(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()
    minority_report = reviewers()
    panel = minority_report["reviewers"]
    assert isinstance(panel, list)
    fable = panel[0]
    assert isinstance(fable, dict)
    fable["verdict"] = "needs-human"
    fable["action"] = {"action_id": "human_valve", "params": {"reason": "architecture"}}

    result = consensus.consensus(
        request=request(repo=repo, question="anthropic minority report"),
        responses=minority_report,
        state_dir=tmp_path / "state-minority-report",
    )

    assert result["outcome"] == "escalate"
    assert result["reason"] == "needs_human"
    assert "dissent" not in result


def test_insufficient_information_is_a_first_class_escalation(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()
    insufficient = reviewers()
    insufficient_panel = insufficient["reviewers"]
    assert isinstance(insufficient_panel, list)
    gpt = insufficient_panel[2]
    assert isinstance(gpt, dict)
    gpt["verdict"] = "insufficient-information"
    insufficient_result = consensus.consensus(
        request=request(repo=repo, question="missing evidence"),
        responses=insufficient,
        state_dir=tmp_path / "state-insufficient",
    )
    assert insufficient_result["outcome"] == "escalate"
    assert insufficient_result["reason"] == "insufficient_information"


def test_panel_shape_identity_and_verdict_validation_escalate(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()

    mismatch = consensus.consensus(
        request=request(repo=repo),
        responses={"reviewers": [{"reviewer_id": "fable", "verdict": "unblock"}]},
        state_dir=tmp_path / "state-mismatch",
    )
    assert mismatch["outcome"] == "escalate"
    assert mismatch["reason"] == "panel_size_mismatch"

    unknown_identity = consensus.consensus(
        request=request(repo=repo, question="unknown identity"),
        responses={
            "reviewers": [
                {
                    "reviewer_id": "new-model",
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                },
                {
                    "reviewer_id": "opus",
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                },
                {
                    "reviewer_id": "gpt-sol",
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                },
            ]
        },
        state_dir=tmp_path / "state-unknown",
    )
    assert unknown_identity["outcome"] == "escalate"
    assert unknown_identity["reason"] == "unpinned_model_identity"
    assert unknown_identity["reviewers"][0]["model"] is None

    unknown_verdict = consensus.consensus(
        request=request(repo=repo, question="unknown verdict"),
        responses={
            "reviewers": [
                {
                    "reviewer_id": "fable",
                    "verdict": "maybe",
                    "action": {"action_id": "work_item_file", "params": {}},
                },
                {
                    "reviewer_id": "opus",
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                },
                {
                    "reviewer_id": "gpt-sol",
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                },
                "ignored free-form peer",
            ]
        },
        state_dir=tmp_path / "state-verdict",
    )
    assert unknown_verdict["outcome"] == "escalate"
    assert unknown_verdict["reason"] == "unknown_verdict"


def test_prompt_text_and_cache_key_normalize_question_noise(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    prompt = module("foreman_consensus_prompt")
    repo = tmp_path / "repo"
    repo.mkdir()
    dirty_question = "\x1b[31mShould I continue?\x1b[0m ⠋ Ctx: 12% left"
    clean_question = "Should I continue?"

    assert prompt.strip_question_region(text=dirty_question) == clean_question
    assert prompt.cache_key(
        request=request(repo=repo, question=dirty_question)
    ) == prompt.cache_key(request=request(repo=repo, question=clean_question))
    assert prompt.snapshot_key_fields(request={"snapshot": "bad"})["repo"] == ""
    assert prompt.canonical_json(value={"b": 1, "a": 2}) == '{"a":2,"b":1}'

    result = consensus.consensus(
        request=request(repo=repo, question="prompt text"),
        responses=reviewers(),
        state_dir=tmp_path / "state-prompts",
        emit_prompts=True,
    )
    prompt_text = "\n".join(str(item["prompt"]) for item in result["prompts"])
    assert "fewer escalations" not in prompt_text
    assert "minimize escalation" not in prompt_text
    assert "avoid human" not in prompt_text
    assert "untrusted evidence" in prompt_text


def test_cache_edges_handle_missing_malformed_stale_and_invalid_records(*, tmp_path: Path):
    cache = module("foreman_consensus_cache")

    assert cache.daily_count(state_dir=tmp_path / "missing-state") == 0
    assert cache.int_field(payload={"panels": True}, key="panels") == 0
    assert cache.record_panel_result(state_dir=tmp_path / "noop") is True

    malformed_cache = tmp_path / "malformed-cache"
    malformed_cache_path = cache.cache_path(state_dir=malformed_cache, key="bad-json")
    malformed_cache_path.parent.mkdir(parents=True)
    malformed_cache_path.write_text("{", encoding="utf-8")
    assert cache.read_cached_verdict(state_dir=malformed_cache, key="bad-json") is None

    malformed_budget = tmp_path / "malformed-budget"
    budget_path = cache.daily_path(state_dir=malformed_budget)
    budget_path.parent.mkdir(parents=True)
    budget_path.write_text("{", encoding="utf-8")
    assert cache.daily_count(state_dir=malformed_budget) == 0

    stale_key = "abc"
    cache.write_json(
        path=cache.cache_path(state_dir=tmp_path / "cache-state", key=stale_key),
        payload={"written_at_epoch": 1, "ttl_seconds": 1, "verdict": {"outcome": "old"}},
    )
    assert cache.read_cached_verdict(state_dir=tmp_path / "cache-state", key=stale_key) is None

    bad_cache_key = "bad"
    cache.write_json(
        path=cache.cache_path(state_dir=tmp_path / "cache-state", key=bad_cache_key),
        payload={"written_at_epoch": 1, "ttl_seconds": 10_000_000_000, "verdict": "bad"},
    )
    assert cache.read_cached_verdict(state_dir=tmp_path / "cache-state", key=bad_cache_key) is None


def test_panel_budget_and_caps_are_enforced_by_exceeding_them(*, tmp_path: Path):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()

    assert (
        consensus.consensus(
            request=request(repo=repo, question="concurrency"),
            responses=reviewers(),
            state_dir=tmp_path / "state-concurrency",
            limits=consensus.PanelLimits(concurrency_cap=0),
        )["reason"]
        == "concurrency_cap_exceeded"
    )
    assert (
        consensus.consensus(
            request=request(repo=repo, question="per tick"),
            responses=reviewers(),
            state_dir=tmp_path / "state-per-tick",
            limits=consensus.PanelLimits(per_tick_panel_budget=0),
        )["reason"]
        == "per_tick_panel_budget_exceeded"
    )
    assert (
        consensus.consensus(
            request=request(repo=repo, question="daily"),
            responses=reviewers(),
            state_dir=tmp_path / "state-daily",
            limits=consensus.PanelLimits(daily_panel_budget=0),
        )["reason"]
        == "daily_panel_budget_exceeded"
    )


def test_main_loads_json_emits_result_and_handles_malformed_input(*, tmp_path: Path, capsys):
    consensus = module("foreman_consensus")
    repo = tmp_path / "repo"
    repo.mkdir()
    request_path = tmp_path / "request.json"
    reviewers_path = tmp_path / "reviewers.json"
    request_path.write_text(json.dumps(request(repo=repo)), encoding="utf-8")
    reviewers_path.write_text(json.dumps(reviewers()), encoding="utf-8")

    exit_code = consensus.main(
        argv=[
            "--request",
            str(request_path),
            "--reviewer-responses",
            str(reviewers_path),
            "--state-dir",
            str(tmp_path / "state"),
            "--emit-prompts",
        ]
    )
    captured = capsys.readouterr()
    emitted = json.loads(captured.out)

    assert exit_code == 0
    assert emitted["outcome"] == "unanimous"
    assert len(emitted["prompts"]) == 3
    assert consensus.load_object(path=request_path)["item_id"] == "overseer-a7c"

    request_path.write_text("{", encoding="utf-8")
    assert consensus.load_object(path=request_path) is None

    exit_code = consensus.main(
        argv=[
            "--request",
            str(request_path),
            "--reviewer-responses",
            str(reviewers_path),
            "--state-dir",
            str(tmp_path / "state-bad"),
        ]
    )
    captured = capsys.readouterr()
    emitted = json.loads(captured.out)

    assert exit_code == 0
    assert emitted["outcome"] == "escalate"
    assert emitted["reason"] == "malformed_input"
