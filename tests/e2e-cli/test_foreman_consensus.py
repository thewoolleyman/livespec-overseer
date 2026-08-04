"""Shipped-artifact tests for the Phase C report-only consensus panel."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / ".claude-plugin" / "bin" / "foreman-consensus"


def _scrubbed_env() -> dict[str, str]:
    removed = {"PYTHONPATH", "COVERAGE_PROCESS_START"}
    return {
        key: value
        for key, value in os.environ.items()
        if key not in removed and not key.startswith("COV_CORE_")
    }


def _request(*, repo: Path, question: str = "Should I run the formatter now?") -> dict[str, object]:
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


def _typed_reviewers(*, action_id: str = "work_item_file") -> dict[str, object]:
    action = {"action_id": action_id, "params": {"target": "overseer-next"}}
    return {
        "reviewers": [
            {"reviewer_id": "fable", "verdict": "unblock", "action": action},
            {"reviewer_id": "opus", "verdict": "unblock", "action": action},
            {"reviewer_id": "gpt-sol", "verdict": "unblock", "action": action},
        ]
    }


def _run_panel(
    *,
    tmp_path: Path,
    request: dict[str, object],
    reviewers: dict[str, object],
    extra: list[str] | None = None,
) -> dict[str, object]:
    assert ENTRYPOINT.is_file()
    request_path = tmp_path / "request.json"
    reviewers_path = tmp_path / "reviewers.json"
    state_dir = tmp_path / "state"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    reviewers_path.write_text(json.dumps(reviewers), encoding="utf-8")
    completed = subprocess.run(  # noqa: S603
        [
            str(ENTRYPOINT),
            "--request",
            str(request_path),
            "--reviewer-responses",
            str(reviewers_path),
            "--state-dir",
            str(state_dir),
            *(extra or []),
        ],
        cwd=tmp_path,
        env=_scrubbed_env(),
        check=False,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Traceback" not in completed.stdout + completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    return parsed


def test_three_agreeing_typed_verdicts_unify_by_string_equality_and_free_form_escalates(
    *, tmp_path: Path
):
    repo = tmp_path / "repo"
    repo.mkdir()

    unanimous = _run_panel(
        tmp_path=tmp_path,
        request=_request(repo=repo),
        reviewers=_typed_reviewers(),
    )

    assert unanimous["outcome"] == "unanimous"
    assert unanimous["action"] == {
        "action_id": "work_item_file",
        "params": {"target": "overseer-next"},
    }
    assert unanimous["mutated"] is False

    free_form = _typed_reviewers()
    reviewers = free_form["reviewers"]
    assert isinstance(reviewers, list)
    free_reviewer = reviewers[1]
    assert isinstance(free_reviewer, dict)
    free_reviewer["action"] = "just tell the worker to continue"

    escalated = _run_panel(
        tmp_path=tmp_path,
        request=_request(repo=repo, question="Different blocked question?"),
        reviewers=free_form,
    )

    assert escalated["outcome"] == "escalate"
    assert escalated["reason"] == "free_form_action"
    assert escalated["action"] == {"action_id": "human_valve", "params": {}}


def test_non_anthropic_needs_human_dissent_is_non_overridable(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reviewers = _typed_reviewers()
    panel = reviewers["reviewers"]
    assert isinstance(panel, list)
    dissent = panel[2]
    assert isinstance(dissent, dict)
    dissent["verdict"] = "needs-human"
    dissent["action"] = {"action_id": "human_valve", "params": {"reason": "architecture"}}

    result = _run_panel(tmp_path=tmp_path, request=_request(repo=repo), reviewers=reviewers)

    assert result["outcome"] == "escalate"
    assert result["reason"] == "non_anthropic_needs_human_dissent"
    assert result["dissent"]["reviewer_id"] == "gpt-sol"


def test_reviewer_prompts_omit_escalation_minimizing_framing(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = _run_panel(
        tmp_path=tmp_path,
        request=_request(repo=repo),
        reviewers=_typed_reviewers(),
        extra=["--emit-prompts"],
    )

    prompts = result["prompts"]
    assert isinstance(prompts, list)
    assert len(prompts) == 3
    prompt_text = "\n".join(str(prompt["prompt"]) for prompt in prompts if isinstance(prompt, dict))
    assert "fewer escalations" not in prompt_text
    assert "minimize escalation" not in prompt_text
    assert "avoid human" not in prompt_text
    assert "Escalation taxonomy" in prompt_text
    assert "untrusted evidence" in prompt_text


def test_panel_budget_and_daily_cap_are_enforced_by_exceeding_them(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    per_tick = _run_panel(
        tmp_path=tmp_path,
        request=_request(repo=repo),
        reviewers=_typed_reviewers(),
        extra=["--per-tick-panel-budget", "0"],
    )
    assert per_tick["outcome"] == "budget_exceeded"
    assert per_tick["reason"] == "per_tick_panel_budget_exceeded"

    daily = _run_panel(
        tmp_path=tmp_path,
        request=_request(repo=repo, question="A fresh question with no cache"),
        reviewers=_typed_reviewers(),
        extra=["--daily-panel-budget", "0"],
    )
    assert daily["outcome"] == "budget_exceeded"
    assert daily["reason"] == "daily_panel_budget_exceeded"
