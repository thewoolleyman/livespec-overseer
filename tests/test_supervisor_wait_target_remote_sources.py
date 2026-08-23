"""Repo-level mirrors for remote wait-target source regressions."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

import _supervisor_wait_target_sources as sources
import wait_premises

__all__: list[str] = []


@dataclass(frozen=True, kw_only=True)
class Completed:
    returncode: int
    stdout: str = ""


def test_wait_target_forge_probe_runs_all_states_and_fails_closed(*, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    calls = []
    assert hasattr(sources, "forge_pull_request_present")

    def raise_timeout(*args, **kwargs):
        calls.append((args, kwargs))
        raise subprocess.TimeoutExpired(cmd="gh", timeout=1)

    monkeypatch.setattr(sources.subprocess, "run", raise_timeout)
    assert not sources.forge_pull_request_present(repo=repo, branch="feat/x")

    def run_match(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed(returncode=0, stdout=json.dumps([{"headRefName": "feat/x"}]))

    monkeypatch.setattr(sources.subprocess, "run", run_match)
    assert sources.forge_pull_request_present(repo=repo, branch="refs/heads/feat/x")
    assert calls[-1][0][0] == [
        "gh",
        "pr",
        "list",
        "--state",
        "all",
        "--head",
        "feat/x",
        "--json",
        "headRefName,number,state",
    ]
    assert calls[-1][1]["cwd"] == repo
    assert calls[-1][1]["timeout"] > 0


def test_wait_premise_writer_preserves_verifier_optional_fields(*, tmp_path):
    repo = tmp_path / "repo"
    _ = wait_premises.write_wait_premise(
        repo=repo,
        topic="alpha",
        kind="fabro-run",
        target_id="01M0RUN",
        evidence_source="fabro ps -a --json --factory=hp",
        recorded_at="2026-08-19T02:30:00Z",
        recheck_by="2026-08-19T03:00:00Z",
        publish_branch="feat/overseer-x",
        work_item_id="overseer-x",
    )

    assert wait_premises.read_wait_premises(repo=repo, topic="alpha")[0] == {
        "schema_version": 1,
        "kind": "fabro-run",
        "target_id": "01M0RUN",
        "evidence_source": "fabro ps -a --json --factory=hp",
        "recorded_at": "2026-08-19T02:30:00Z",
        "recheck_by": "2026-08-19T03:00:00Z",
        "publish_branch": "feat/overseer-x",
        "work_item_id": "overseer-x",
    }
