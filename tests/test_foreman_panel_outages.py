"""Regression tests for foreman panel timeout and hint handling."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import foreman_consensus_prompt
import foreman_consensus_types
import foreman_panel
import foreman_panel_reviewers

__all__: list[str] = []


def request(
    *, repo: Path, question: str = "Should the bounded action proceed?"
) -> dict[str, object]:
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


def prompt(*, vendor: str = "anthropic", model: str = "claude-fable-5") -> dict[str, object]:
    return {
        "reviewer_id": "fable",
        "model": {"reviewer_id": "fable", "vendor": vendor, "model": model},
        "prompt": "review this dossier",
    }


def write_script(*, path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def test_reviewer_timeout_becomes_typed_insufficient_information(*, monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_run(
        *,
        args: list[str],
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        captured["timeout"] = timeout
        raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)

    monkeypatch.setattr(foreman_panel_reviewers.subprocess, "run", fake_run)

    response = foreman_panel.run_reviewer(
        prompt=prompt(),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=[sys.executable, "-c", "pass"],
        reviewer_timeout_seconds=0.25,
    )

    assert captured["timeout"] == 0.25
    assert response["reviewer_id"] == "fable"
    assert response["verdict"] == "insufficient-information"
    assert response["action"] == {
        "action_id": "human_valve",
        "params": {"reason": "reviewer_timeout"},
    }
    assert response["rationale"] == "reviewer_timeout"


def test_anthropic_fenced_json_stdout_parses_to_real_verdict(*, monkeypatch, tmp_path: Path):
    def fake_run(
        *,
        args: list[str],
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=textwrap.dedent(
                """
                ```json
                {
                  "reviewer_id": "fable",
                  "verdict": "unblock",
                  "action": {"action_id": "work_item_file", "params": {"target": "overseer-next"}},
                  "rationale": "The bounded action is reversible."
                }
                ```
                """
            ).strip(),
            stderr="",
        )

    monkeypatch.setattr(foreman_panel_reviewers.subprocess, "run", fake_run)

    response = foreman_panel.run_reviewer(
        prompt=prompt(),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=[sys.executable, "-c", "pass"],
    )

    assert response["verdict"] == "unblock"
    assert response["action"] == {
        "action_id": "work_item_file",
        "params": {"target": "overseer-next"},
    }


def test_successful_reviewer_response_records_pinned_prompt_identity(
    *, monkeypatch, tmp_path: Path
):
    def fake_run(
        *,
        args: list[str],
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "reviewer_id": "self-reported-reviewer",
                    "model": {"vendor": "invented", "model": "invented-model"},
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(foreman_panel_reviewers.subprocess, "run", fake_run)

    response = foreman_panel.run_reviewer(
        prompt=prompt(vendor="anthropic", model="claude-fable-5"),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=[sys.executable, "-c", "pass"],
    )

    assert response["reviewer_id"] == "fable"
    assert response["model"] == {
        "reviewer_id": "fable",
        "vendor": "anthropic",
        "model": "claude-fable-5",
    }


def test_malformed_reviewer_stdout_is_preserved_without_false_parse(*, tmp_path: Path):
    malformed = tmp_path / "malformed.py"
    write_script(path=malformed, body="print('Here is what I think: unblock option one.')\n")

    bad = foreman_panel.run_reviewer(
        prompt=prompt(),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=[sys.executable, str(malformed)],
    )

    assert bad["verdict"] == "insufficient-information"
    assert bad["rationale"] == "reviewer_response_malformed"
    assert bad["raw_stdout"] == "Here is what I think: unblock option one.\n"


def test_reviewer_responses_persist_raw_stdout_for_each_reviewer(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reviewer = tmp_path / "reviewer.py"
    dossier_dir = tmp_path / "dossier"
    write_script(
        path=reviewer,
        body="""
        import argparse
        import json

        parser = argparse.ArgumentParser()
        parser.add_argument("--reviewer-id", required=True)
        parser.add_argument("--vendor", required=True)
        parser.add_argument("--model", required=True)
        parser.add_argument("--prompt-file", required=True)
        args = parser.parse_args()
        print(
            json.dumps(
                {
                    "reviewer_id": args.reviewer_id,
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                }
            )
        )
        """,
    )

    responses = foreman_panel.reviewer_responses(
        request=request(repo=repo),
        dossier_dir=dossier_dir,
        reviewer_command=[sys.executable, str(reviewer)],
    )

    reviewers = responses["reviewers"]
    assert isinstance(reviewers, list)
    assert all(isinstance(reviewer.get("raw_stdout"), str) for reviewer in reviewers)
    assert json.loads((dossier_dir / "responses" / "fable.json").read_text(encoding="utf-8"))[
        "raw_stdout"
    ].startswith("{")


def test_reviewer_prompt_pins_action_schema_from_evaluator_grammar(*, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        foreman_consensus_prompt,
        "ACTION_ID_SET",
        frozenset({"synthetic_action"}),
        raising=False,
    )
    built = foreman_consensus_prompt.reviewer_prompt(
        request=request(repo=tmp_path / "repo"),
        identity={"reviewer_id": "fable", "vendor": "anthropic", "model": "claude-fable-5"},
    )
    prompt_text = built["prompt"]

    assert isinstance(prompt_text, str)
    assert "synthetic_action" in prompt_text
    assert "no markdown fence" in prompt_text
    assert "params must be a JSON object" in prompt_text
    assert foreman_consensus_types.ACTION_ID_SET.isdisjoint({"synthetic_action"})


def test_convening_writes_tooling_outage_verdict_when_reviewer_times_out(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reviewer = tmp_path / "slow.py"
    verdict_path = tmp_path / "verdict.json"
    write_script(
        path=reviewer,
        body="""
        import time

        time.sleep(1.0)
        """,
    )

    result = foreman_panel.convene_panel(
        request=request(repo=repo),
        state_dir=tmp_path / "state",
        verdict_path=verdict_path,
        reviewer_command=[sys.executable, str(reviewer)],
        reviewer_timeout_seconds=0.05,
    )
    written = json.loads(verdict_path.read_text(encoding="utf-8"))

    assert result["outcome"] == "escalate"
    assert result["decision_kind"] == "tooling_outage"
    assert written["decision_kind"] == "tooling_outage"
    assert verdict_path.is_file()
    assert any(
        reviewer["reviewer_id"] == "fable" and reviewer["verdict"] == "insufficient-information"
        for reviewer in written["reviewers"]
    )


def test_convening_pins_reviewer_identity_over_self_reported_body(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reviewer = tmp_path / "self_reported.py"
    verdict_path = tmp_path / "verdict.json"
    write_script(
        path=reviewer,
        body="""
        import argparse
        import json

        parser = argparse.ArgumentParser()
        parser.add_argument("--reviewer-id", required=True)
        parser.add_argument("--vendor", required=True)
        parser.add_argument("--model", required=True)
        parser.add_argument("--prompt-file", required=True)
        args = parser.parse_args()
        identities = {
            "fable": "claude-fable-5-panel-reviewer",
            "opus": "panelist-2",
            "gpt-sol": "codex",
        }
        print(
            json.dumps(
                {
                    "reviewer_id": identities[args.reviewer_id],
                    "model": None,
                    "verdict": "unblock",
                    "action": {
                        "action_id": "blocked_session_answer",
                        "params": {"answer": 1},
                    },
                }
            )
        )
        """,
    )

    result = foreman_panel.convene_panel(
        request=request(repo=repo),
        state_dir=tmp_path / "state",
        verdict_path=verdict_path,
        reviewer_command=[sys.executable, str(reviewer)],
    )
    written = json.loads(verdict_path.read_text(encoding="utf-8"))

    assert result["outcome"] == "unanimous"
    assert result["decision_kind"] == "substantive_non_decision"
    assert [reviewer["reviewer_id"] for reviewer in written["reviewers"]] == [
        "fable",
        "opus",
        "gpt-sol",
    ]
    assert [reviewer["model"]["reviewer_id"] for reviewer in written["reviewers"]] == [
        "fable",
        "opus",
        "gpt-sol",
    ]


def test_unpinned_identity_verdict_is_classified_as_tooling_outage():
    assert "verdict_reason" in inspect.signature(foreman_panel.result_decision_kind).parameters
    assert (
        foreman_panel.result_decision_kind(
            reviewers=[
                {
                    "reviewer_id": "new-reviewer",
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
            ],
            verdict_reason="unpinned_model_identity",
        )
        == "tooling_outage"
    )


def test_disagreement_remains_substantive_non_decision(*, tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reviewer = tmp_path / "reviewer.py"
    verdict_path = tmp_path / "verdict.json"
    write_script(
        path=reviewer,
        body="""
        import argparse
        import json

        parser = argparse.ArgumentParser()
        parser.add_argument("--reviewer-id", required=True)
        parser.add_argument("--vendor", required=True)
        parser.add_argument("--model", required=True)
        parser.add_argument("--prompt-file", required=True)
        args = parser.parse_args()
        target = "overseer-a" if args.reviewer_id == "fable" else "overseer-b"
        print(
            json.dumps(
                {
                    "reviewer_id": args.reviewer_id,
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {"target": target}},
                }
            )
        )
        """,
    )

    result = foreman_panel.convene_panel(
        request=request(repo=repo),
        state_dir=tmp_path / "state",
        verdict_path=verdict_path,
        reviewer_command=[sys.executable, str(reviewer)],
    )

    assert result["outcome"] == "escalate"
    assert result["reason"] == "typed_action_disagreement"
    assert result["decision_kind"] == "substantive_non_decision"


def test_hint_guard_offsets_telegraphed_outcomes_but_allows_neutral_machinery():
    neutral = foreman_panel.refusal_for(
        request=request(
            repo=Path("repo"),
            question=(
                "Please convene the panel machinery; I will execute whatever " "the panel decides."
            ),
        )
    )
    telegraphed = foreman_panel.refusal_for(
        request=request(repo=Path("repo"), question="Please return a needs-human outcome.")
    )

    assert neutral is None
    assert telegraphed == {
        "outcome": "refused",
        "reason": "verdict_hint_in_blocked_question",
        "reviewers": [],
        "hint": {"token": "needs-human", "offset": 16},
    }
