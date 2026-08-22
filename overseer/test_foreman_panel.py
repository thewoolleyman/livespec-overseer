"""Beside-tests for the foreman consensus panel convenor."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

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


def write_script(*, path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def prompt(*, vendor: str = "anthropic", model: str = "claude-fable-5") -> dict[str, object]:
    return {
        "reviewer_id": "fable",
        "model": {"reviewer_id": "fable", "vendor": vendor, "model": model},
        "prompt": "review this dossier",
    }


def test_default_paths_and_commands_cover_anthropic_and_codex_shapes(*, tmp_path: Path):
    relative = request(repo=Path("relative-repo"))

    assert foreman_panel.default_dossier_dir(request=relative, key="abc") == (
        Path("tmp") / "overseer" / "foreman" / "panel" / "abc"
    )
    assert foreman_panel.default_reviewer_command(
        prompt="hello",
        model={"vendor": "anthropic", "model": "claude-fable-5"},
    ) == ["claude", "--model", "claude-fable-5", "-p", "hello"]
    assert foreman_panel.default_reviewer_command(
        prompt="hello",
        model={"vendor": "openai", "model": "gpt-5.6-sol"},
    ) == ["codex", "exec", "--model", "gpt-5.6-sol", "hello"]
    assert foreman_panel.reviewer_argv(
        command=None,
        prompt=prompt(vendor="openai", model="gpt-5.6-sol"),
        prompt_file=tmp_path / "prompt.json",
    ) == ["codex", "exec", "--model", "gpt-5.6-sol", "review this dossier"]


def test_default_reviewer_missing_command_becomes_insufficient_information(*, monkeypatch):
    monkeypatch.setattr(foreman_panel_reviewers.shutil, "which", lambda name: None)

    response = foreman_panel.run_reviewer(
        prompt=prompt(vendor="openai", model="gpt-5.6-sol"),
        prompt_file=Path("prompt.json"),
        reviewer_command=None,
    )

    assert response["reviewer_id"] == "fable"
    assert response["verdict"] == "insufficient-information"
    assert response["rationale"] == "reviewer command not found: codex"


def test_default_reviewer_existing_command_runs_and_parses_response(*, monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_run(
        *,
        args: list[str],
        check: bool,
        capture_output: bool,
        stdin: object,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["check"] = check
        captured["capture_output"] = capture_output
        captured["stdin"] = stdin
        captured["text"] = text
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                {
                    "reviewer_id": "fable",
                    "verdict": "unblock",
                    "action": {"action_id": "work_item_file", "params": {}},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(foreman_panel_reviewers.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(foreman_panel_reviewers.subprocess, "run", fake_run)

    response = foreman_panel.run_reviewer(
        prompt=prompt(),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=None,
    )

    assert captured["args"] == ["claude", "--model", "claude-fable-5", "-p", "review this dossier"]
    assert captured["stdin"] is subprocess.DEVNULL
    assert response["verdict"] == "unblock"


def test_reviewer_failures_are_typed_insufficient_information(*, tmp_path: Path):
    failing = tmp_path / "failing.py"
    malformed = tmp_path / "malformed.py"
    write_script(path=failing, body="raise SystemExit(7)\n")
    write_script(path=malformed, body="print('not json')\n")

    failed = foreman_panel.run_reviewer(
        prompt=prompt(),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=[sys.executable, str(failing)],
    )
    bad = foreman_panel.run_reviewer(
        prompt=prompt(),
        prompt_file=tmp_path / "prompt.json",
        reviewer_command=[sys.executable, str(malformed)],
    )

    assert failed["rationale"] == "reviewer_command_failed"
    assert bad["rationale"] == "reviewer_response_malformed"


def test_cli_refuses_malformed_request_and_writes_success_verdict(*, tmp_path: Path, capsys):
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    non_object = tmp_path / "non-object.json"
    non_object.write_text("null", encoding="utf-8")
    refused_code = foreman_panel.main(
        argv=[
            "--request",
            str(malformed),
            "--verdict-output",
            str(tmp_path / "refused.json"),
        ]
    )
    refused = json.loads(capsys.readouterr().out)
    non_object_code = foreman_panel.main(
        argv=[
            "--request",
            str(non_object),
            "--verdict-output",
            str(tmp_path / "non-object-refused.json"),
        ]
    )
    non_object_refused = json.loads(capsys.readouterr().out)

    repo = tmp_path / "repo"
    repo.mkdir()
    reviewer = tmp_path / "reviewer.py"
    request_path = tmp_path / "request.json"
    verdict_path = tmp_path / "verdict.json"
    request_path.write_text(json.dumps(request(repo=repo)), encoding="utf-8")
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
                    "action": {
                        "action_id": "work_item_file",
                        "params": {"target": "overseer-next"},
                    },
                }
            )
        )
        """,
    )

    success_code = foreman_panel.main(
        argv=[
            "--request",
            str(request_path),
            "--verdict-output",
            str(verdict_path),
            "--state-dir",
            str(tmp_path / "state"),
            "--dossier-dir",
            str(tmp_path / "dossier"),
            "--reviewer-command",
            f"{sys.executable} {reviewer}",
        ]
    )
    success = json.loads(capsys.readouterr().out)

    assert refused_code == 2
    assert refused["reason"] == "malformed_request"
    assert non_object_code == 2
    assert non_object_refused["reason"] == "malformed_request"
    assert success_code == 0
    assert success["outcome"] == "unanimous"
    assert verdict_path.is_file()
